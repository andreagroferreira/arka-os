"""Tests for core.sync.engine — orchestrator and CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.sync.engine import (
    _parse_scan_dirs,
    _read_current_version,
    _read_previous_version,
    _read_repo_path,
    _resolve_features_dir,
    run_sync,
)
from core.sync.schema import SyncReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_yaml(features_dir: Path, name: str = "test-feature") -> None:
    features_dir.mkdir(parents=True, exist_ok=True)
    (features_dir / f"{name}.yaml").write_text(
        f"name: {name}\n"
        "added_in: '2.0.0'\n"
        "mandatory: true\n"
        "section_title: Test Feature\n"
        "detection_pattern: test-pattern\n"
        "deprecated_in: null\n"
        "content: |\n"
        "  Test content.\n"
    )


# ---------------------------------------------------------------------------
# TestReadPreviousVersion
# ---------------------------------------------------------------------------


class TestReadPreviousVersion:
    def test_returns_pending_sync_when_file_missing(self, tmp_path: Path) -> None:
        result = _read_previous_version(tmp_path)
        assert result == "pending-sync"

    def test_reads_version_from_state_file(self, tmp_path: Path) -> None:
        state = {"version": "2.13.0", "last_sync": "2026-01-01T00:00:00Z"}
        (tmp_path / "sync-state.json").write_text(json.dumps(state))
        result = _read_previous_version(tmp_path)
        assert result == "2.13.0"

    def test_returns_pending_sync_on_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "sync-state.json").write_text("not-json")
        result = _read_previous_version(tmp_path)
        assert result == "pending-sync"

    def test_returns_pending_sync_when_version_missing(self, tmp_path: Path) -> None:
        (tmp_path / "sync-state.json").write_text(json.dumps({"last_sync": "x"}))
        result = _read_previous_version(tmp_path)
        assert result == "pending-sync"


# ---------------------------------------------------------------------------
# TestReadRepoPath
# ---------------------------------------------------------------------------


class TestReadRepoPath:
    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        result = _read_repo_path(tmp_path)
        assert result is None

    def test_reads_repo_path(self, tmp_path: Path) -> None:
        (tmp_path / ".repo-path").write_text("/some/repo/path\n")
        result = _read_repo_path(tmp_path)
        assert result == Path("/some/repo/path")

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / ".repo-path").write_text("")
        result = _read_repo_path(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# TestReadCurrentVersion
# ---------------------------------------------------------------------------


class TestReadCurrentVersion:
    def test_returns_unknown_when_no_repo_path(self, tmp_path: Path) -> None:
        result = _read_current_version(tmp_path)
        assert result == "unknown"

    def test_reads_version_from_repo(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "VERSION").write_text("v2.14.0\n")
        (tmp_path / ".repo-path").write_text(str(repo_dir))
        result = _read_current_version(tmp_path)
        assert result == "v2.14.0"

    def test_returns_unknown_when_version_file_missing(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (tmp_path / ".repo-path").write_text(str(repo_dir))
        result = _read_current_version(tmp_path)
        assert result == "unknown"


# ---------------------------------------------------------------------------
# TestResolveFeaturesDir
# ---------------------------------------------------------------------------


class TestResolveFeaturesDir:
    def test_returns_repo_features_when_exists(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        features_dir = repo_dir / "core" / "sync" / "features"
        features_dir.mkdir(parents=True)
        (tmp_path / ".repo-path").write_text(str(repo_dir))

        result = _resolve_features_dir(tmp_path)
        assert result == features_dir

    def test_falls_back_to_config_dir(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (tmp_path / ".repo-path").write_text(str(repo_dir))

        result = _resolve_features_dir(tmp_path)
        assert result == tmp_path / "config" / "sync" / "features"

    def test_falls_back_when_no_repo_path(self, tmp_path: Path) -> None:
        result = _resolve_features_dir(tmp_path)
        assert result == tmp_path / "config" / "sync" / "features"


# ---------------------------------------------------------------------------
# TestParseScanDirs
# ---------------------------------------------------------------------------


class TestParseScanDirs:
    def test_single_path(self) -> None:
        result = _parse_scan_dirs("/Users/test/herd")
        assert result == [Path("/Users/test/herd")]

    def test_two_paths_with_descriptions(self) -> None:
        result = _parse_scan_dirs(
            "/Users/test/herd para projectos laravel, /Users/test/work para projectos Nuxt"
        )
        assert result == [Path("/Users/test/herd"), Path("/Users/test/work")]

    def test_ignores_non_path_segments(self) -> None:
        result = _parse_scan_dirs("no path here, /valid/path")
        assert result == [Path("/valid/path")]

    def test_empty_string(self) -> None:
        result = _parse_scan_dirs("")
        assert result == []


# ---------------------------------------------------------------------------
# TestRunSync
# ---------------------------------------------------------------------------


def _setup_env(tmp_path: Path) -> dict:
    """Create a minimal sync environment for integration tests."""
    arkaos_home = tmp_path / "arkaos_home"
    arkaos_home.mkdir()

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "VERSION").write_text("v2.14.0\n")

    features_dir = repo_dir / "core" / "sync" / "features"
    _make_feature_yaml(features_dir)

    (arkaos_home / ".repo-path").write_text(str(repo_dir))
    (arkaos_home / "sync-state.json").write_text(
        json.dumps({"version": "2.13.0", "last_sync": "2026-01-01T00:00:00Z"})
    )
    (arkaos_home / "profile.json").write_text(
        json.dumps({"projectsDir": ""})
    )

    skills_dir = tmp_path / "skills"
    mcps_dir = skills_dir / "arka" / "mcps"
    mcps_dir.mkdir(parents=True)
    (mcps_dir / "registry.json").write_text(json.dumps({"mcpServers": {}}))

    projects_dir = skills_dir / "arka" / "projects"
    projects_dir.mkdir(parents=True)

    knowledge_dir = skills_dir / "arka" / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "ecosystems.json").write_text(json.dumps({"ecosystems": {}}))

    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))

    return {
        "arkaos_home": arkaos_home,
        "skills_dir": skills_dir,
        "home_path": str(tmp_path),
    }


class TestRunSync:
    def test_full_sync(self, tmp_path: Path) -> None:
        env = _setup_env(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=None
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        assert isinstance(report, SyncReport)
        assert report.previous_version == "2.13.0"
        assert report.current_version == "v2.14.0"

    def test_full_sync_returns_mcp_results(self, tmp_path: Path) -> None:
        env = _setup_env(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=None
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        assert isinstance(report.mcp_results, list)
        assert isinstance(report.settings_results, list)
        assert isinstance(report.descriptor_results, list)

    def test_sync_writes_state(self, tmp_path: Path) -> None:
        env = _setup_env(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=None
        ):
            run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        state_file = env["arkaos_home"] / "sync-state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["version"] == "v2.14.0"  # VERSION file has v-prefix

    def test_sync_first_run(self, tmp_path: Path) -> None:
        env = _setup_env(tmp_path)
        (env["arkaos_home"] / "sync-state.json").unlink()

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=None
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        assert report.previous_version == "pending-sync"
        assert report.current_version == "v2.14.0"
