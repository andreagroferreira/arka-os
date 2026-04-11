"""Engine Orchestrator for the ArkaOS Sync Engine.

Coordinates all sync phases and provides a CLI entry point for /arka update.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from core.sync.manifest import build_manifest
from core.sync.discovery import discover_all_projects
from core.sync.mcp_syncer import sync_all_mcps
from core.sync.settings_syncer import sync_all_settings
from core.sync.descriptor_syncer import sync_all_descriptors
from core.sync.reporter import build_report, format_report, write_sync_state
from core.sync.schema import SyncReport


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_sync(arkaos_home: Path, skills_dir: Path, home_path: str) -> SyncReport:
    """Orchestrate all deterministic sync phases and return a SyncReport."""
    previous_version = _read_previous_version(arkaos_home)
    current_version = _read_current_version(arkaos_home)
    features_dir = _resolve_features_dir(arkaos_home)

    build_manifest(previous_version, current_version, features_dir)

    projects = _discover_projects(arkaos_home, skills_dir)

    registry_path = skills_dir / "arka" / "mcps" / "registry.json"
    mcp_results = sync_all_mcps(projects, registry_path, home_path)
    settings_results = sync_all_settings(mcp_results)
    descriptor_results = sync_all_descriptors(projects)

    report = build_report(
        previous_version,
        current_version,
        mcp_results,
        settings_results,
        descriptor_results,
        [],
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
        home_path=str(Path(args.home).parent),
    )

    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(format_report(report))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _read_previous_version(arkaos_home: Path) -> str:
    """Read version field from sync-state.json, defaulting to pending-sync."""
    state_file = arkaos_home / "sync-state.json"
    if not state_file.exists():
        return "pending-sync"
    try:
        data = json.loads(state_file.read_text())
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
        return version_file.read_text().strip()
    except OSError:
        return "unknown"


def _read_repo_path(arkaos_home: Path) -> Path | None:
    """Read the absolute repo path from .repo-path file."""
    repo_path_file = arkaos_home / ".repo-path"
    if not repo_path_file.exists():
        return None
    try:
        raw = repo_path_file.read_text().strip()
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
    """Combine profile.json dirs, descriptor dir, and ecosystems into projects."""
    descriptor_dir = skills_dir / "arka" / "projects"
    ecosystems_file = skills_dir / "arka" / "knowledge" / "ecosystems.json"

    scan_dirs = _load_scan_dirs_from_profile(arkaos_home)

    return discover_all_projects(descriptor_dir, scan_dirs, ecosystems_file)


def _load_scan_dirs_from_profile(arkaos_home: Path) -> list[Path]:
    """Read projectsDir from profile.json and parse into scan directory paths."""
    profile_file = arkaos_home / "profile.json"
    if not profile_file.exists():
        return []
    try:
        data = json.loads(profile_file.read_text())
        projects_dir_str = data.get("projectsDir", "")
        if not projects_dir_str:
            return []
        return _parse_scan_dirs(projects_dir_str)
    except (json.JSONDecodeError, OSError):
        return []


if __name__ == "__main__":
    sys.exit(main())
