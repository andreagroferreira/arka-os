"""MCP syncer for the ArkaOS Sync Engine.

Syncs .mcp.json files for all projects based on the MCP registry
and the detected stack. Custom (non-registry) MCPs are preserved.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from core.sync.schema import McpSyncResult, Project

# Maps stack item names to registry categories
_STACK_TO_CATEGORIES: dict[str, list[str]] = {
    "laravel": ["laravel"],
    "nuxt": ["nuxt"],
    "vue": ["nuxt"],
    "next": ["react"],
    "react": ["react"],
    "shopify": ["ecommerce"],
}

# Keys that are registry metadata — stripped when writing .mcp.json
_REGISTRY_META_KEYS = {"category", "description", "required_env"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_registry(registry_path: Path) -> dict:
    """Load registry.json and return the mcpServers dict.

    Returns {} if the file is missing or cannot be parsed.
    """
    if not registry_path.exists():
        return {}
    try:
        data = json.loads(registry_path.read_text())
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_mcps_for_stack(
    registry: dict, stack: list[str]
) -> list[tuple[str, dict]]:
    """Return (name, config) tuples from registry that apply to the given stack.

    Always includes the "base" category. Maps stack items to categories via
    _STACK_TO_CATEGORIES.
    """
    allowed: set[str] = {"base"}
    for item in stack:
        for category in _STACK_TO_CATEGORIES.get(item, []):
            allowed.add(category)

    result: list[tuple[str, dict]] = []
    for name, config in registry.items():
        if config.get("category") in allowed:
            result.append((name, config))
    return result


def sync_project_mcp(
    project: Project, registry: dict, home_path: str
) -> McpSyncResult:
    """Sync the .mcp.json file for a single project.

    Reads the current .mcp.json, calculates the target MCPs from the registry
    and project stack, and writes a merged result that includes both target MCPs
    and custom (user-added) MCPs not present in the registry.
    """
    try:
        return _do_sync_mcp(project, registry, home_path)
    except Exception as exc:  # noqa: BLE001
        return McpSyncResult(
            path=project.path,
            status="error",
            error=str(exc),
        )


def _do_sync_mcp(
    project: Project, registry: dict, home_path: str
) -> McpSyncResult:
    """Execute the MCP sync logic for a single project."""
    mcp_file = Path(project.path) / ".mcp.json"
    is_new = not mcp_file.is_file()

    current = _read_current_mcps(mcp_file)
    target_raw = resolve_mcps_for_stack(registry, project.stack)
    target = _resolve_placeholders(target_raw, home_path, project.path)
    registry_names = set(registry.keys())

    added, removed, updated, preserved = _diff_mcps(
        current, target, registry_names, registry
    )

    if not added and not removed and not updated:
        return McpSyncResult(
            path=project.path,
            status="unchanged",
            final_mcp_list=sorted(current.keys()),
        )

    merged = _build_merged(current, target, registry_names, registry)
    _write_mcp_json(mcp_file, merged)
    status = "created" if is_new else "updated"

    return McpSyncResult(
        path=project.path,
        status=status,
        mcps_added=sorted(added),
        mcps_removed=sorted(removed),
        mcps_updated=sorted(updated),
        mcps_preserved=sorted(preserved),
        final_mcp_list=sorted(merged.keys()),
    )


def sync_all_mcps(
    projects: list[Project],
    registry_path: Path,
    home_path: str,
) -> list[McpSyncResult]:
    """Sync .mcp.json for all projects, loading the registry once."""
    registry = load_registry(registry_path)
    return [sync_project_mcp(p, registry, home_path) for p in projects]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _read_current_mcps(mcp_file: Path) -> dict:
    """Read the current .mcp.json and return its mcpServers dict."""
    if not mcp_file.exists():
        return {}
    try:
        data = json.loads(mcp_file.read_text())
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_placeholders(
    target: list[tuple[str, dict]],
    home_path: str,
    project_path: str,
) -> list[tuple[str, dict]]:
    """Replace {home} and {cwd} placeholders in MCP config values."""
    resolved: list[tuple[str, dict]] = []
    for name, config in target:
        config_copy = copy.deepcopy(config)
        _replace_in_dict(config_copy, "{home}", home_path)
        _replace_in_dict(config_copy, "{cwd}", project_path)
        resolved.append((name, config_copy))
    return resolved


def _replace_in_dict(obj: dict, placeholder: str, value: str) -> None:
    """Recursively replace placeholder strings in dict values (in-place)."""
    for key, val in obj.items():
        if isinstance(val, str):
            obj[key] = val.replace(placeholder, value)
        elif isinstance(val, list):
            obj[key] = [
                item.replace(placeholder, value) if isinstance(item, str) else item
                for item in val
            ]
        elif isinstance(val, dict):
            _replace_in_dict(val, placeholder, value)


def _strip_meta_keys(config: dict) -> dict:
    """Return a copy of config with registry metadata keys removed."""
    return {k: v for k, v in config.items() if k not in _REGISTRY_META_KEYS}


def _find_updated(
    current: dict,
    target: list[tuple[str, dict]],
) -> list[str]:
    """Return names of MCPs that exist in both current and target but differ.

    Comparison ignores registry metadata keys (category, description, etc.).
    """
    updated: list[str] = []
    target_dict = dict(target)
    for name in current:
        if name not in target_dict:
            continue
        current_clean = _strip_meta_keys(current[name])
        target_clean = _strip_meta_keys(target_dict[name])
        if current_clean != target_clean:
            updated.append(name)
    return updated


def _diff_mcps(
    current: dict,
    target: list[tuple[str, dict]],
    registry_names: set[str],
    full_registry: dict,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Compute the diff between current and target MCPs.

    Returns (added, removed, updated, preserved) name lists.
    - added: in target but not in current
    - removed: in registry AND in current but NOT in target (recategorized/removed)
    - updated: in both current and target but config differs
    - preserved: in current, NOT in registry (user-added custom MCPs)
    """
    target_names = {name for name, _ in target}

    added = [name for name, _ in target if name not in current]
    removed = [
        name
        for name in current
        if name in registry_names and name not in target_names
    ]
    updated = _find_updated(current, target)
    preserved = [name for name in current if name not in registry_names]

    return added, removed, updated, preserved


def _build_merged(
    current: dict,
    target: list[tuple[str, dict]],
    registry_names: set[str],
    full_registry: dict,
) -> dict:
    """Build the merged mcpServers dict: target MCPs + preserved custom MCPs."""
    merged: dict = {}

    for name, config in target:
        merged[name] = _strip_meta_keys(config)

    for name, config in current.items():
        if name not in registry_names:
            merged[name] = _strip_meta_keys(config)

    return merged


def _write_mcp_json(mcp_file: Path, servers: dict) -> None:
    """Write the mcpServers dict to .mcp.json with 2-space indentation."""
    payload = {"mcpServers": servers}
    mcp_file.write_text(json.dumps(payload, indent=2) + "\n")
