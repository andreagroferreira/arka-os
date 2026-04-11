"""Tests for core.sync.settings_syncer — settings.local.json sync."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sync.schema import McpSyncResult, SettingsSyncResult
from core.sync.settings_syncer import sync_all_settings, sync_project_settings


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_mcp_result(path: str, servers: list[str]) -> McpSyncResult:
    return McpSyncResult(
        path=path,
        status="updated",
        final_mcp_list=servers,
    )


def _settings_file(project_path: Path) -> Path:
    return project_path / ".claude" / "settings.local.json"


def _read_settings(project_path: Path) -> dict:
    return json.loads(_settings_file(project_path).read_text())


# ---------------------------------------------------------------------------
# TestSyncProjectSettings
# ---------------------------------------------------------------------------


class TestSyncProjectSettings:
    def test_create_new_settings(self, tmp_path: Path) -> None:
        """No existing file → creates with default permissions + sorted servers."""
        servers = ["arka-prompts", "context7", "laravel-boost"]
        result = sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), servers))

        assert result.status == "updated"
        assert result.error is None
        assert set(result.servers_added) == set(servers)
        assert result.servers_removed == []

        data = _read_settings(tmp_path)
        assert data["enableAllProjectMcpServers"] is True
        assert data["enabledMcpjsonServers"] == sorted(servers)
        assert data["permissions"] == {"allow": ["Read", "Grep", "Glob", "WebFetch"]}

    def test_update_existing_preserves_permissions(self, tmp_path: Path) -> None:
        """Existing file with custom Bash rules must survive intact."""
        existing = {
            "permissions": {
                "allow": [
                    "Read",
                    "Grep",
                    "Glob",
                    "Bash(php artisan:*)",
                    "Bash(composer:*)",
                ]
            },
            "enabledMcpjsonServers": ["arka-prompts"],
            "enableAllProjectMcpServers": True,
        }
        sf = _settings_file(tmp_path)
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(existing, indent=2))

        new_servers = ["arka-prompts", "context7", "laravel-boost"]
        result = sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), new_servers))

        assert result.status == "updated"
        data = _read_settings(tmp_path)
        # Permissions must be completely unchanged
        assert data["permissions"] == existing["permissions"]
        assert "Bash(php artisan:*)" in data["permissions"]["allow"]
        assert data["enabledMcpjsonServers"] == sorted(new_servers)

    def test_unchanged_when_already_correct(self, tmp_path: Path) -> None:
        """Same servers + flag already set → status is unchanged, no write needed."""
        servers = sorted(["context7", "arka-prompts"])
        existing = {
            "permissions": {"allow": ["Read"]},
            "enabledMcpjsonServers": servers,
            "enableAllProjectMcpServers": True,
        }
        sf = _settings_file(tmp_path)
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(existing, indent=2))

        result = sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), servers))

        assert result.status == "unchanged"
        assert result.servers_added == []
        assert result.servers_removed == []
        assert result.error is None

    def test_add_and_remove_servers(self, tmp_path: Path) -> None:
        """Tracks servers added and removed between current and target."""
        existing = {
            "permissions": {"allow": ["Read"]},
            "enabledMcpjsonServers": ["arka-prompts", "old-server"],
            "enableAllProjectMcpServers": True,
        }
        sf = _settings_file(tmp_path)
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(existing, indent=2))

        new_servers = ["arka-prompts", "context7"]
        result = sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), new_servers))

        assert result.status == "updated"
        assert "context7" in result.servers_added
        assert "old-server" in result.servers_removed
        assert "arka-prompts" not in result.servers_added
        assert "arka-prompts" not in result.servers_removed

        data = _read_settings(tmp_path)
        assert data["enabledMcpjsonServers"] == sorted(new_servers)

    def test_flag_false_triggers_update(self, tmp_path: Path) -> None:
        """enableAllProjectMcpServers=False with correct servers still triggers update."""
        servers = sorted(["arka-prompts", "context7"])
        existing = {
            "permissions": {"allow": ["Read"]},
            "enabledMcpjsonServers": servers,
            "enableAllProjectMcpServers": False,
        }
        sf = _settings_file(tmp_path)
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(existing, indent=2))

        result = sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), servers))

        assert result.status == "updated"
        data = _read_settings(tmp_path)
        assert data["enableAllProjectMcpServers"] is True

    def test_creates_dot_claude_directory(self, tmp_path: Path) -> None:
        """The .claude/ directory is created if it doesn't exist."""
        assert not (tmp_path / ".claude").exists()

        sync_project_settings(tmp_path, _make_mcp_result(str(tmp_path), ["arka-prompts"]))

        assert (tmp_path / ".claude").is_dir()
        assert _settings_file(tmp_path).exists()


# ---------------------------------------------------------------------------
# TestSyncAllSettings
# ---------------------------------------------------------------------------


class TestSyncAllSettings:
    def test_batch_sync(self, tmp_path: Path) -> None:
        """Two projects are synced and both results are returned."""
        p1 = tmp_path / "project-one"
        p2 = tmp_path / "project-two"
        p1.mkdir()
        p2.mkdir()

        mcp_results = [
            _make_mcp_result(str(p1), ["arka-prompts", "laravel-boost"]),
            _make_mcp_result(str(p2), ["arka-prompts", "context7"]),
        ]

        results = sync_all_settings(mcp_results)

        assert len(results) == 2
        paths = {r.path for r in results}
        assert str(p1) in paths
        assert str(p2) in paths

        d1 = _read_settings(p1)
        d2 = _read_settings(p2)
        assert "laravel-boost" in d1["enabledMcpjsonServers"]
        assert "laravel-boost" not in d2["enabledMcpjsonServers"]
        assert "context7" in d2["enabledMcpjsonServers"]

    def test_empty_list_returns_empty(self) -> None:
        """Empty input produces empty output."""
        assert sync_all_settings([]) == []
