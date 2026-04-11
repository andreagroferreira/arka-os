"""Tests for core.sync.reporter — sync report builder, state writer, and formatter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sync.reporter import build_report, format_report, write_sync_state
from core.sync.schema import (
    DescriptorSyncResult,
    McpSyncResult,
    SettingsSyncResult,
    SkillSyncResult,
    SyncReport,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mcp(path: str, status: str = "unchanged", added: list[str] | None = None, error: str | None = None) -> McpSyncResult:
    return McpSyncResult(path=path, status=status, mcps_added=added or [], error=error)


def _settings(path: str, status: str = "unchanged", error: str | None = None) -> SettingsSyncResult:
    return SettingsSyncResult(path=path, status=status, error=error)


def _descriptor(path: str, status: str = "unchanged", changes: list[str] | None = None, error: str | None = None) -> DescriptorSyncResult:
    return DescriptorSyncResult(path=path, status=status, changes=changes or [], error=error)


def _skill(name: str, status: str = "unchanged", features_added: list[str] | None = None, error: str | None = None) -> SkillSyncResult:
    return SkillSyncResult(skill_name=name, status=status, features_added=features_added or [], error=error)


# ---------------------------------------------------------------------------
# TestBuildReport
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_empty_report(self) -> None:
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])

        assert report.previous_version == "v2.13.0"
        assert report.current_version == "v2.14.0"
        assert report.mcp_results == []
        assert report.settings_results == []
        assert report.descriptor_results == []
        assert report.skill_results == []
        assert report.errors == []

    def test_report_with_results(self) -> None:
        mcp_results = [_mcp("/p/app1", "updated"), _mcp("/p/app2", "unchanged")]
        settings_results = [_settings("/p/app1", "updated")]
        descriptor_results = [_descriptor("/p/app1", "unchanged")]
        skill_results = [_skill("client_retail", "updated")]

        report = build_report("v2.13.0", "v2.14.0", mcp_results, settings_results, descriptor_results, skill_results)

        assert len(report.mcp_results) == 2
        assert len(report.settings_results) == 1
        assert len(report.descriptor_results) == 1
        assert len(report.skill_results) == 1
        assert report.errors == []

    def test_report_collects_errors_from_all_phases(self) -> None:
        mcp_results = [_mcp("/p/app1", "error", error="write failed")]
        settings_results = [_settings("/p/app2", "error", error="permission denied")]
        descriptor_results = [_descriptor("/p/app3", "error", error="yaml parse error")]
        skill_results = [_skill("client_commerce", "error", error="missing file")]

        report = build_report("v2.13.0", "v2.14.0", mcp_results, settings_results, descriptor_results, skill_results)

        assert len(report.errors) == 4
        assert any("MCP" in e for e in report.errors)
        assert any("Settings" in e for e in report.errors)
        assert any("Descriptor" in e for e in report.errors)
        assert any("Skill" in e for e in report.errors)

    def test_no_error_when_error_field_is_none(self) -> None:
        results = [_mcp("/p/app1", "updated"), _mcp("/p/app2", "unchanged")]
        report = build_report("v2.13.0", "v2.14.0", results, [], [], [])
        assert report.errors == []

    def test_versions_preserved(self) -> None:
        report = build_report("v1.0.0", "v2.0.0", [], [], [], [])
        assert report.previous_version == "v1.0.0"
        assert report.current_version == "v2.0.0"


# ---------------------------------------------------------------------------
# TestWriteSyncState
# ---------------------------------------------------------------------------


class TestWriteSyncState:
    def test_writes_correct_json(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        report = build_report(
            "v2.13.0",
            "v2.14.0",
            [_mcp("/p/app1"), _mcp("/p/app2")],
            [],
            [],
            [_skill("client_retail"), _skill("client_commerce")],
        )

        write_sync_state(state_file, report)

        data = json.loads(state_file.read_text())
        assert data["version"] == "v2.14.0"
        assert "last_sync" in data
        assert data["projects_synced"] == 2
        assert data["skills_synced"] == 2
        assert data["errors"] == []

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        state_file = tmp_path / "nested" / "deep" / "state.json"
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])

        write_sync_state(state_file, report)

        assert state_file.exists()

    def test_counts_unique_project_paths(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        mcp_results = [
            _mcp("/p/app1"),
            _mcp("/p/app1"),  # duplicate path
            _mcp("/p/app2"),
        ]
        report = build_report("v2.13.0", "v2.14.0", mcp_results, [], [], [])

        write_sync_state(state_file, report)

        data = json.loads(state_file.read_text())
        assert data["projects_synced"] == 2  # unique paths only

    def test_errors_included_in_state(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        report = build_report(
            "v2.13.0",
            "v2.14.0",
            [_mcp("/p/app1", "error", error="boom")],
            [],
            [],
            [],
        )

        write_sync_state(state_file, report)

        data = json.loads(state_file.read_text())
        assert len(data["errors"]) == 1
        assert "boom" in data["errors"][0]

    def test_last_sync_is_iso8601_utc(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])

        write_sync_state(state_file, report)

        data = json.loads(state_file.read_text())
        # ISO 8601 UTC strings contain '+00:00' or end with 'Z'
        assert "+00:00" in data["last_sync"] or data["last_sync"].endswith("Z")


# ---------------------------------------------------------------------------
# TestFormatReport
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_format_contains_version_header(self) -> None:
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])
        output = format_report(report)
        assert "v2.13.0 → v2.14.0" in output

    def test_format_contains_separator(self) -> None:
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])
        output = format_report(report)
        assert "=" * 55 in output

    def test_format_shows_phase_counts(self) -> None:
        mcp_results = [
            _mcp("/p/app1", "updated"),
            _mcp("/p/app2", "updated"),
            _mcp("/p/app3", "unchanged"),
        ]
        settings_results = [
            _settings("/p/app1", "updated"),
            _settings("/p/app2", "unchanged"),
        ]
        report = build_report("v2.13.0", "v2.14.0", mcp_results, settings_results, [], [])
        output = format_report(report)

        assert "3 synced (2 updated, 1 unchanged)" in output
        assert "2 synced (1 updated, 1 unchanged)" in output

    def test_format_shows_key_changes_for_mcp_additions(self) -> None:
        mcp_results = [
            _mcp("/projects/crm-app", "updated", added=["laravel-boost"]),
            _mcp("/projects/web-app", "updated", added=["laravel-boost"]),
        ]
        report = build_report("v2.13.0", "v2.14.0", mcp_results, [], [], [])
        output = format_report(report)

        assert "Key changes:" in output
        assert "laravel-boost" in output
        assert "crm-app" in output
        assert "web-app" in output

    def test_format_shows_paused_projects(self) -> None:
        descriptor_results = [
            _descriptor("/projects/lora-tester", "updated", changes=["status changed: active → paused"]),
        ]
        report = build_report("v2.13.0", "v2.14.0", [], [], descriptor_results, [])
        output = format_report(report)

        assert "Auto-paused" in output
        assert "lora-tester" in output

    def test_format_shows_skill_feature_additions(self) -> None:
        skill_results = [
            _skill("client_commerce", "updated", features_added=["forge"]),
            _skill("client_retail", "updated", features_added=["forge"]),
        ]
        report = build_report("v2.13.0", "v2.14.0", [], [], [], skill_results)
        output = format_report(report)

        assert "forge" in output
        assert "client_commerce" in output

    def test_format_empty_report_no_key_changes_section(self) -> None:
        report = build_report("v2.13.0", "v2.14.0", [], [], [], [])
        output = format_report(report)

        assert "Key changes:" not in output
        assert "Errors: 0" in output

    def test_format_shows_error_count(self) -> None:
        mcp_results = [_mcp("/p/app1", "error", error="failed")]
        report = build_report("v2.13.0", "v2.14.0", mcp_results, [], [], [])
        output = format_report(report)

        assert "Errors: 1" in output

    def test_format_skills_line_label(self) -> None:
        skill_results = [_skill("client_retail", "updated"), _skill("client_commerce", "unchanged")]
        report = build_report("v2.13.0", "v2.14.0", [], [], [], skill_results)
        output = format_report(report)

        assert "ecosystems synced" in output
        assert "2 ecosystems synced (1 updated, 1 unchanged)" in output
