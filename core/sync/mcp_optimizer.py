"""MCP Optimizer — narrows the active MCP list per project via policy,
AI fallback, and per-project override; injects env secrets from a vault;
generates .env.arkaos.example for missing values.

Runs between mcp_syncer (produces full .mcp.json) and settings_syncer
(writes enabledMcpjsonServers). Deferred MCPs are simply absent from the
returned ``final_mcp_list`` — their definitions remain in ``.mcp.json``
so user can opt-in later.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import yaml

from core.sync.ai_mcp_decider import decide_ambiguous
from core.sync.policy_loader import decide, load_policy
from core.sync.schema import McpSyncResult, Project


def optimize_project_mcps(
    project: Project,
    mcp_result: McpSyncResult,
    policy_path: Path,
    vault_path: Path | None,
    cache_path: Path,
    call_ai=None,
) -> McpSyncResult:
    """Return a new McpSyncResult with deferred MCPs removed from final_mcp_list."""
    try:
        return _do_optimize(project, mcp_result, policy_path, vault_path, cache_path, call_ai)
    except Exception as exc:  # noqa: BLE001
        return mcp_result.model_copy(update={
            "optimizer_warnings": list(mcp_result.optimizer_warnings) + [f"optimization failed: {exc}"],
        })


def _do_optimize(
    project: Project,
    mcp_result: McpSyncResult,
    policy_path: Path,
    vault_path: Path | None,
    cache_path: Path,
    call_ai=None,
) -> McpSyncResult:
    if mcp_result.status == "error" or not mcp_result.final_mcp_list:
        return mcp_result

    warnings: list[str] = list(mcp_result.optimizer_warnings)

    policy = load_policy(policy_path)
    pd = decide(policy, mcp_result.final_mcp_list, project.stack, project.ecosystem)
    ai_decisions = decide_ambiguous(
        pd.ambiguous, project.stack, project.ecosystem, cache_path, call_ai
    )

    active = set(pd.active)
    deferred = set(pd.deferred)
    for name, decision in ai_decisions.items():
        (active if decision == "active" else deferred).add(name)

    override, override_warnings = _load_override(Path(project.path))
    warnings.extend(override_warnings)

    # Fix 3: collision handling — force_active takes precedence
    force_active = set(override.get("force_active", []))
    force_deferred = set(override.get("force_deferred", []))
    collisions = force_active & force_deferred
    for c in sorted(collisions):
        warnings.append(f"override collision for MCP '{c}': force_active takes precedence")

    active = (active | force_active) - (force_deferred - force_active)
    deferred = (deferred - force_active) | (force_deferred - force_active)

    inject_warnings = _inject_env_vars(Path(project.path), vault_path, project.name)
    warnings.extend(inject_warnings)

    return mcp_result.model_copy(update={
        "final_mcp_list": sorted(active),
        "mcps_deferred": sorted(deferred),
        "optimizer_warnings": warnings,
    })


def _load_override(project_path: Path) -> tuple[dict, list[str]]:
    """Load per-project override YAML. Returns (data, warnings)."""
    override = project_path / ".arkaos" / "mcp-override.yaml"
    if not override.exists():
        return {}, []
    try:
        return yaml.safe_load(override.read_text()) or {}, []
    except (yaml.YAMLError, OSError) as exc:
        return {}, [f"override YAML parse error: {exc}"]


def _merge_env(servers: dict, merged_env: dict) -> tuple[bool, dict[str, str]]:
    """Inject known env vars into server configs. Returns (changed, missing)."""
    missing: dict[str, str] = {}
    changed = False
    for server_name, config in servers.items():
        env = config.get("env") or {}
        for var_name, current in env.items():
            if current:
                continue
            if var_name in merged_env:
                env[var_name] = merged_env[var_name]
                changed = True
            else:
                missing[var_name] = server_name
        if env:
            config["env"] = env
    return changed, missing


def _inject_env_vars(project_path: Path, vault_path: Path | None, project_name: str) -> list[str]:
    """Inject vault secrets into .mcp.json env vars. Returns warnings."""
    mcp_file = project_path / ".mcp.json"
    if not mcp_file.exists():
        return []

    try:
        data = json.loads(mcp_file.read_text())
    except (json.JSONDecodeError, OSError):
        return [".mcp.json malformed; skipped env injection"]

    servers = data.get("mcpServers", {})
    vault, vault_warnings = _load_vault(vault_path) if vault_path else ({}, [])

    global_env = vault.get("global", {})
    project_env = vault.get("per_project", {}).get(project_name, {})
    merged_env = {**global_env, **project_env}

    changed, missing = _merge_env(servers, merged_env)

    if changed:
        mcp_file.write_text(json.dumps(data, indent=2) + "\n")

    if missing:
        _write_env_example(project_path, missing)

    return vault_warnings


def _load_vault(path: Path) -> tuple[dict, list[str]]:
    """Load the secrets vault JSON. Returns (data, warnings)."""
    if not path.exists():
        return {}, []
    try:
        st = path.stat()
    except OSError:
        return {}, []
    # Refuse world- or group-readable files
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        return {}, ["vault permissions too permissive (group/world readable); secrets not injected"]
    try:
        return json.loads(path.read_text()), []
    except (json.JSONDecodeError, OSError):
        return {}, ["vault JSON parse error; secrets not injected"]


def _write_env_example(project_path: Path, missing: dict[str, str]) -> None:
    lines = ["# Auto-generated by ArkaOS MCP Optimizer", ""]
    for var, server in sorted(missing.items()):
        lines.append(f"# required by {server}")
        lines.append(f"{var}=")
    (project_path / ".env.arkaos.example").write_text("\n".join(lines) + "\n")


def optimize_all_mcps(
    projects: list[Project],
    mcp_results: list[McpSyncResult],
    policy_path: Path,
    vault_path: Path | None,
    cache_path: Path,
) -> list[McpSyncResult]:
    by_path = {r.path: r for r in mcp_results}
    out: list[McpSyncResult] = []
    for p in projects:
        mr = by_path.get(p.path)
        if mr is None:
            continue
        out.append(optimize_project_mcps(p, mr, policy_path, vault_path, cache_path))
    return out
