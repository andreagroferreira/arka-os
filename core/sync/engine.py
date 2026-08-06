"""Engine Orchestrator for the ArkaOS Sync Engine.

Coordinates all sync phases and provides a CLI entry point for /arka update.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from core.runtime.user_paths import (
    ecosystems_file as resolve_ecosystems_file,
)
from core.runtime.user_paths import (
    projects_dir as resolve_projects_dir,
)
from core.sync.agent_provisioner import sync_all_agents
from core.sync.content_syncer import sync_all_content
from core.sync.descriptor_syncer import sync_all_descriptors
from core.sync.discovery import discover_all_projects
from core.sync.manifest import build_manifest
from core.sync.mcp_optimizer import optimize_all_mcps
from core.sync.mcp_syncer import sync_all_mcps
from core.sync.migration_runner import (
    load_migrations,
    pending_migrations,
    run_migrations,
)
from core.sync.reporter import build_report, format_report, write_sync_state
from core.sync.schema import MigrationScanResult, SyncReport
from core.sync.settings_syncer import sync_all_settings

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_sync(arkaos_home: Path, skills_dir: Path, home_path: str) -> SyncReport:
    """Orchestrate all deterministic sync phases and return a SyncReport."""
    previous_version = _read_previous_version(arkaos_home)
    current_version = _read_current_version(arkaos_home)
    features_dir = _resolve_features_dir(arkaos_home)

    manifest = build_manifest(previous_version, current_version, features_dir)

    projects = _discover_projects(arkaos_home, skills_dir)

    mcp_results = _run_mcp_phase(projects, skills_dir, home_path)

    settings_results = sync_all_settings(mcp_results)
    descriptor_results = sync_all_descriptors(projects)
    content_results = sync_all_content(projects)
    agent_results = sync_all_agents(projects)

    migrations = _run_migration_phase(
        arkaos_home, projects, previous_version, current_version, manifest.is_first_sync
    )

    report = build_report(
        previous_version,
        current_version,
        mcp_results,
        settings_results,
        descriptor_results,
        [],
        content_results=content_results,
        agent_results=agent_results,
        new_features=manifest.new_features,
        deprecated_features=manifest.deprecated_features,
        migrations=migrations,
    )

    state_file = arkaos_home / "sync-state.json"
    write_sync_state(state_file, report)

    return report


def main() -> None:
    """CLI entry point for the sync engine."""
    parser = argparse.ArgumentParser(description="ArkaOS Sync Engine")
    parser.add_argument("--home", required=True, help="ArkaOS home directory")
    parser.add_argument("--skills", required=True, help="Skills directory")
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    args = parser.parse_args()

    report = run_sync(
        arkaos_home=Path(args.home),
        skills_dir=Path(args.skills),
        home_path=str(Path.home()),
    )

    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(format_report(report))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _run_mcp_phase(projects: list, skills_dir: Path, home_path: str) -> list:
    """Sync .mcp.json for every project, then apply the policy optimizer."""
    registry_path = skills_dir / "arka" / "mcps" / "registry.json"
    results = sync_all_mcps(projects, registry_path, home_path)

    policy_path = Path(__file__).resolve().parents[2] / "config" / "mcp-policy.yaml"
    if not policy_path.exists():
        return results
    vault_path = Path.home() / ".arkaos" / "secrets.json"
    return optimize_all_mcps(
        projects,
        results,
        policy_path,
        vault_path if vault_path.exists() else None,
        Path.home() / ".arkaos" / "mcp-decisions.cache.json",
    )


def _run_migration_phase(
    arkaos_home: Path,
    projects: list,
    previous_version: str,
    current_version: str,
    is_first_sync: bool,
) -> MigrationScanResult:
    """Phase 6 — propose-only migrations for the versions this upgrade crossed."""
    specs, load_errors = load_migrations(_resolve_migrations_dir(arkaos_home))
    return run_migrations(
        projects,
        pending_migrations(specs, previous_version, is_first_sync),
        arkaos_home / "migration-proposals",
        current_version,
        pre_errors=load_errors,
    )


def _read_previous_version(arkaos_home: Path) -> str:
    """Read version field from sync-state.json, defaulting to pending-sync."""
    state_file = arkaos_home / "sync-state.json"
    if not state_file.exists():
        return "pending-sync"
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return data.get("version", "pending-sync") or "pending-sync"
    except (json.JSONDecodeError, OSError):
        return "pending-sync"


def _read_current_version(arkaos_home: Path) -> str:
    """Read version from VERSION file in the ArkaOS repo."""
    repo_path = _read_repo_path(arkaos_home)
    if repo_path is None:
        return "unknown"
    version_file = repo_path / "VERSION"
    if not version_file.exists():
        return "unknown"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _read_repo_path(arkaos_home: Path) -> Path | None:
    """Read the absolute repo path from .repo-path file."""
    repo_path_file = arkaos_home / ".repo-path"
    if not repo_path_file.exists():
        return None
    try:
        raw = repo_path_file.read_text(encoding="utf-8").strip()
        return Path(raw) if raw else None
    except OSError:
        return None


def _resolve_features_dir(arkaos_home: Path) -> Path:
    """Resolve the features directory from repo or fallback config."""
    repo_path = _read_repo_path(arkaos_home)
    if repo_path is not None:
        repo_features = repo_path / "core" / "sync" / "features"
        if repo_features.exists():
            return repo_features

    fallback = arkaos_home / "config" / "sync" / "features"
    return fallback


def _resolve_migrations_dir(arkaos_home: Path) -> Path:
    """Resolve the migrations directory from repo or fallback config."""
    repo_path = _read_repo_path(arkaos_home)
    if repo_path is not None:
        repo_migrations = repo_path / "core" / "sync" / "migrations"
        if repo_migrations.exists():
            return repo_migrations
    return arkaos_home / "config" / "sync" / "migrations"


def _parse_scan_dirs(projects_dir_str: str) -> list[Path]:
    """Parse a projectsDir string, extracting all paths starting with /."""
    segments = re.split(r",\s*", projects_dir_str.strip())
    paths: list[Path] = []
    for segment in segments:
        match = re.match(r"(/[^\s]+)", segment.strip())
        if match:
            paths.append(Path(match.group(1)))
    return paths


def _discover_projects(arkaos_home: Path, skills_dir: Path) -> list:
    """Combine profile.json dirs, descriptor dir, and ecosystems into projects.

    Project descriptors and the ecosystems registry are user-local data and
    live under ~/.arkaos/ (see ADR 2026-04-17-user-data-separation). During
    the deprecation window, reads fall back to the legacy paths under
    skills_dir with a one-shot warning. `skills_dir` is kept in the
    signature for backward compatibility and test ergonomics but is no
    longer consulted for user data.
    """
    del skills_dir  # retained for signature stability; unused.

    # resolve_*() returns None when neither the new nor legacy path exists.
    # `discover_all_projects` requires concrete Path objects but calls
    # `.exists()` internally, so substituting the (non-existent) canonical
    # path keeps the contract: missing → returns an empty project list.
    descriptor_dir = resolve_projects_dir() or (Path.home() / ".arkaos" / "projects")
    ecosystems_path = resolve_ecosystems_file() or (
        Path.home() / ".arkaos" / "ecosystems.json"
    )

    scan_dirs = _load_scan_dirs_from_profile(arkaos_home)

    return discover_all_projects(descriptor_dir, scan_dirs, ecosystems_path)


def _load_scan_dirs_from_profile(arkaos_home: Path) -> list[Path]:
    """Read projectsDir from profile.json and parse into scan directory paths."""
    profile_file = arkaos_home / "profile.json"
    if not profile_file.exists():
        return []
    try:
        data = json.loads(profile_file.read_text(encoding="utf-8"))
        projects_dir_str = data.get("projectsDir", "")
        if not projects_dir_str:
            return []
        return _parse_scan_dirs(projects_dir_str)
    except (json.JSONDecodeError, OSError):
        return []


if __name__ == "__main__":
    sys.exit(main())
