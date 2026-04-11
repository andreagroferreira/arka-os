"""Settings syncer for the ArkaOS Sync Engine.

Syncs .claude/settings.local.json for each project based on MCP sync results.
Permissions are NEVER modified — custom Bash rules and other user config survive.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.sync.schema import McpSyncResult, SettingsSyncResult

_DEFAULT_PERMISSIONS: dict = {"allow": ["Read", "Grep", "Glob", "WebFetch"]}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_project_settings(
    project_path: Path, mcp_result: McpSyncResult
) -> SettingsSyncResult:
    """Sync .claude/settings.local.json for a single project.

    Reads the current settings file (if any), compares enabledMcpjsonServers
    and enableAllProjectMcpServers against the target derived from mcp_result,
    and writes an updated file only when a change is needed.

    Permissions are always preserved. When the file does not exist it is
    created with _DEFAULT_PERMISSIONS.
    """
    try:
        return _do_sync(project_path, mcp_result)
    except Exception as exc:  # noqa: BLE001
        return SettingsSyncResult(
            path=str(project_path),
            status="error",
            error=str(exc),
        )


def _do_sync(
    project_path: Path, mcp_result: McpSyncResult
) -> SettingsSyncResult:
    """Execute the settings sync logic for a single project."""
    settings_file = project_path / ".claude" / "settings.local.json"
    target_servers = sorted(mcp_result.final_mcp_list)

    current = _read_current_settings(settings_file)
    if _is_already_correct(current, target_servers):
        return SettingsSyncResult(path=str(project_path), status="unchanged")

    added, removed = _compute_diff(current, target_servers)
    merged = _build_merged_settings(current, target_servers)
    _write_settings(settings_file, merged)

    return SettingsSyncResult(
        path=str(project_path),
        status="updated",
        servers_added=added,
        servers_removed=removed,
    )


def sync_all_settings(mcp_results: list[McpSyncResult]) -> list[SettingsSyncResult]:
    """Sync settings.local.json for all projects in mcp_results."""
    return [
        sync_project_settings(Path(r.path), r)
        for r in mcp_results
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _read_current_settings(settings_file: Path) -> dict:
    """Return the parsed settings dict, or {} if the file is missing or invalid."""
    if not settings_file.exists():
        return {}
    try:
        return json.loads(settings_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _is_already_correct(current: dict, target_servers: list[str]) -> bool:
    """Return True when servers and flag already match the target."""
    current_servers = sorted(current.get("enabledMcpjsonServers", []))
    flag = current.get("enableAllProjectMcpServers", False)
    return current_servers == target_servers and flag is True


def _compute_diff(
    current: dict, target_servers: list[str]
) -> tuple[list[str], list[str]]:
    """Return (added, removed) server name lists relative to current settings."""
    current_set = set(current.get("enabledMcpjsonServers", []))
    target_set = set(target_servers)
    added = sorted(target_set - current_set)
    removed = sorted(current_set - target_set)
    return added, removed


def _build_merged_settings(current: dict, target_servers: list[str]) -> dict:
    """Return a new settings dict with updated servers, preserving all permissions."""
    merged = dict(current)
    if "permissions" not in merged:
        merged["permissions"] = _DEFAULT_PERMISSIONS
    merged["enabledMcpjsonServers"] = target_servers
    merged["enableAllProjectMcpServers"] = True
    return merged


def _write_settings(settings_file: Path, data: dict) -> None:
    """Create parent dirs if needed and write settings as 2-space JSON."""
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n")
