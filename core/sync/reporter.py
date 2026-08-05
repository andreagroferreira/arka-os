"""Reporter for the ArkaOS Sync Engine.

Builds the sync report, writes sync state to disk, and formats terminal output.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from core.sync.schema import (
    AgentProvisionResult,
    ContentSyncResult,
    DescriptorSyncResult,
    McpSyncResult,
    MigrationScanResult,
    SettingsSyncResult,
    SkillSyncResult,
    SyncReport,
)

_SEPARATOR = "=" * 55


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_report(
    previous_version: str,
    current_version: str,
    mcp_results: list[McpSyncResult],
    settings_results: list[SettingsSyncResult],
    descriptor_results: list[DescriptorSyncResult],
    skill_results: list[SkillSyncResult],
    new_features: list[str] | None = None,
    deprecated_features: list[str] | None = None,
    content_results: list[ContentSyncResult] | None = None,
    agent_results: list[AgentProvisionResult] | None = None,
    migrations: MigrationScanResult | None = None,
) -> SyncReport:
    """Aggregate all sync results into a SyncReport."""
    phases = (mcp_results, settings_results, descriptor_results, skill_results)
    return SyncReport(
        previous_version=previous_version,
        current_version=current_version,
        new_features=new_features or [],
        deprecated_features=deprecated_features or [],
        mcp_results=mcp_results,
        settings_results=settings_results,
        descriptor_results=descriptor_results,
        skill_results=skill_results,
        content_results=content_results or [],
        agent_results=agent_results or [],
        migrations=migrations,
        errors=_collect_errors(
            *phases, content_results=content_results, agent_results=agent_results
        ),
    )


def write_sync_state(state_file: Path, report: SyncReport) -> None:
    """Write the sync state JSON to disk."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    unique_paths = {r.path for r in report.mcp_results}
    state = {
        "version": report.current_version,
        "last_sync": datetime.now(UTC).isoformat(),
        "projects_synced": len(unique_paths),
        "skills_synced": len(report.skill_results),
        "errors": report.errors,
    }
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def format_report(report: SyncReport) -> str:
    """Format the sync report for terminal output."""
    lines = [
        _SEPARATOR,
        f"  ArkaOS Sync Complete — {report.previous_version} → {report.current_version}",
        _SEPARATOR,
        "",
        _format_phase_line("MCPs", report.mcp_results),
        _format_phase_line("Settings", report.settings_results),
        _format_phase_line("Descriptors", report.descriptor_results),
        _format_skill_line(report.skill_results),
        _format_content_line(report.content_results),
        _format_agents_line(report.agent_results),
    ]

    key_changes = _format_key_changes(report)
    if key_changes:
        lines += ["", "  Key changes:", *[f"  - {c}" for c in key_changes]]

    lines += _format_migration_lines(report.migrations)
    lines += _format_deferred_lines(report.mcp_results)
    lines += ["", f"  Errors: {len(report.errors)}", _SEPARATOR]
    return "\n".join(lines)


def _format_deferred_lines(results: list[McpSyncResult]) -> list[str]:
    """Deferred MCPs, or nothing when none were deferred."""
    total = sum(len(r.mcps_deferred) for r in results)
    if total == 0:
        return []
    projects = sum(1 for r in results if r.mcps_deferred)
    return ["", f"  Deferred MCPs: {total} across {projects} projects."]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _collect_errors(
    mcp: list[McpSyncResult],
    settings: list[SettingsSyncResult],
    desc: list[DescriptorSyncResult],
    skills: list[SkillSyncResult],
    content_results: list[ContentSyncResult] | None = None,
    agent_results: list[AgentProvisionResult] | None = None,
) -> list[str]:
    errors: list[str] = []
    for r in mcp:
        if r.error:
            errors.append(f"MCP({r.path}): {r.error}")
        for w in r.optimizer_warnings:
            errors.append(f"MCP Optimizer({r.path}): {w}")
    for r in settings:
        if r.error:
            errors.append(f"Settings({r.path}): {r.error}")
    for r in desc:
        if r.error:
            errors.append(f"Descriptor({r.path}): {r.error}")
    for r in skills:
        if r.error:
            errors.append(f"Skill({r.skill_name}): {r.error}")
    for r in content_results or []:
        if r.error:
            errors.append(f"Content({r.path}): {r.error}")
        for artefact_error in r.artefacts_errored:
            errors.append(f"Content({r.path}): {artefact_error}")
    for r in agent_results or []:
        if r.error:
            errors.append(f"Agents({r.path}): {r.error}")
        for a in r.agents_errored:
            errors.append(f"Agents({r.path}): missing core file for {a}")
    return errors


def _count_updated(results: list) -> int:
    return sum(1 for r in results if r.status in ("updated", "created"))


def _count_unchanged(results: list) -> int:
    return sum(1 for r in results if r.status == "unchanged")


def _format_phase_line(label: str, results: list) -> str:
    total = len(results)
    updated = _count_updated(results)
    unchanged = _count_unchanged(results)
    return f"  {label + ':':<14}{total} synced ({updated} updated, {unchanged} unchanged)"


def _format_skill_line(results: list[SkillSyncResult]) -> str:
    total = len(results)
    updated = _count_updated(results)
    restamped = sum(1 for r in results if r.status == "restamped")
    unchanged = _count_unchanged(results)
    counts = f"{updated} updated, {unchanged} unchanged"
    if restamped:
        counts = f"{updated} updated, {restamped} restamped, {unchanged} unchanged"
    return f"  {'Skills:':<14}{total} ecosystems synced ({counts})"


def _format_key_changes(report: SyncReport) -> list[str]:
    changes: list[str] = []
    _add_mcp_changes(report.mcp_results, changes)
    _add_descriptor_changes(report.descriptor_results, changes)
    _add_skill_changes(report.skill_results, changes)
    return changes


def _add_mcp_changes(results: list[McpSyncResult], changes: list[str]) -> None:
    added_by_mcp: dict[str, list[str]] = {}
    for r in results:
        for mcp_name in r.mcps_added:
            added_by_mcp.setdefault(mcp_name, []).append(r.path)
    for mcp_name, paths in added_by_mcp.items():
        project_names = [Path(p).name for p in paths]
        changes.append(f"MCP '{mcp_name}' added to: {', '.join(project_names)}")


def _add_descriptor_changes(results: list[DescriptorSyncResult], changes: list[str]) -> None:
    paused: list[str] = []
    archived: list[str] = []
    for r in results:
        for change in r.changes:
            if "paused" in change.lower():
                paused.append(Path(r.path).name)
            elif "archived" in change.lower():
                archived.append(Path(r.path).name)
    if paused:
        changes.append(f"Auto-paused (>30d inactive): {', '.join(paused)}")
    if archived:
        changes.append(f"Auto-archived (path missing): {', '.join(archived)}")


def _add_skill_changes(results: list[SkillSyncResult], changes: list[str]) -> None:
    for r in results:
        for feature in r.features_added:
            changes.append(f"'{feature}' added to: {r.skill_name}")


def _format_migration_lines(migrations: MigrationScanResult | None) -> list[str]:
    """Render the migration section; silent only when nothing ran and nothing hit."""
    if migrations is None or not migrations.migrations_run:
        return []
    ran = len(migrations.migrations_run)
    if not migrations.hits:
        return ["", f"  Migrations: {ran} checked, no legacy patterns found."]
    projects = len({h.project for h in migrations.hits})
    lines = [
        "",
        f"  Migrations: {ran} checked — {len(migrations.hits)} legacy pattern(s) "
        f"in {projects} project(s). Nothing applied.",
        f"  Review: {migrations.proposal_path}",
    ]
    if migrations.truncated:
        lines.append(f"  Capped (more hits exist): {', '.join(migrations.truncated)}")
    return lines


def _format_content_line(results: list[ContentSyncResult]) -> str:
    total = len(results)
    updated = _count_updated(results)
    restamped = sum(1 for r in results if r.status == "restamped")
    unchanged = _count_unchanged(results)
    counts = f"{updated} updated, {unchanged} unchanged"
    if restamped:
        counts = f"{updated} updated, {restamped} restamped, {unchanged} unchanged"
    return f"  {'Content:':<14}{total} synced ({counts})"


def _format_agents_line(results: list[AgentProvisionResult]) -> str:
    total = len(results)
    updated = _count_updated(results)
    unchanged = _count_unchanged(results)
    return f"  {'Agents:':<14}{total} synced ({updated} updated, {unchanged} unchanged)"
