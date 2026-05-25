"""Tests for /api/settings/{mcps,hooks,plugins} (PR63b v2.89.0)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Point HOME at a fresh dir so each test sees clean state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ─── /api/settings/mcps ─────────────────────────────────────────────────


class TestMcpsEndpoint:
    def test_returns_empty_when_no_files(self, dashboard_module, tmp_home):
        result = dashboard_module.settings_mcps()
        assert result["mcps"] == []
        assert result["total"] == 0

    def test_reads_user_global_mcpservers(self, dashboard_module, tmp_home):
        (tmp_home / ".claude.json").write_text(json.dumps({
            "mcpServers": {
                "obsidian": {"command": "npx obsidian-mcp"},
                "playwright": {"command": "npx playwright-mcp"},
            },
        }))
        result = dashboard_module.settings_mcps()
        assert result["total"] == 2
        names = [r["name"] for r in result["mcps"]]
        assert "obsidian" in names
        assert "playwright" in names
        for r in result["mcps"]:
            assert r["source"] == "user-global"
            assert r["transport"] == "stdio"  # command-based → stdio

    def test_merges_arkaos_registry_with_dedup(self, dashboard_module, tmp_home):
        (tmp_home / ".claude.json").write_text(json.dumps({
            "mcpServers": {"obsidian": {"command": "npx obsidian-mcp"}},
        }))
        reg_dir = tmp_home / ".claude" / "skills" / "arka" / "mcps"
        reg_dir.mkdir(parents=True)
        (reg_dir / "registry.json").write_text(json.dumps({
            "servers": {
                "obsidian": {"command": "another"},   # duplicate — drop
                "shopify":  {"command": "shopify-mcp"},
            },
        }))
        result = dashboard_module.settings_mcps()
        names = [r["name"] for r in result["mcps"]]
        assert names.count("obsidian") == 1
        assert "shopify" in names
        obsidian = next(r for r in result["mcps"] if r["name"] == "obsidian")
        # First write wins → user-global keeps the source
        assert obsidian["source"] == "user-global"
        shopify = next(r for r in result["mcps"] if r["name"] == "shopify")
        assert shopify["source"] == "arkaos-registry"

    def test_handles_http_transport(self, dashboard_module, tmp_home):
        (tmp_home / ".claude.json").write_text(json.dumps({
            "mcpServers": {"remote": {"url": "https://mcp.example.com"}},
        }))
        result = dashboard_module.settings_mcps()
        assert result["mcps"][0]["transport"] == "http"

    def test_handles_corrupt_user_global(self, dashboard_module, tmp_home):
        (tmp_home / ".claude.json").write_text("not-json{")
        # Must not raise
        result = dashboard_module.settings_mcps()
        assert result["mcps"] == []

    def test_handles_registry_list_shape(self, dashboard_module, tmp_home):
        """The registry can also ship `servers: [...]` instead of a dict."""
        reg_dir = tmp_home / ".claude" / "skills" / "arka" / "mcps"
        reg_dir.mkdir(parents=True)
        (reg_dir / "registry.json").write_text(json.dumps({
            "servers": [
                {"name": "alpha", "command": "alpha-cmd"},
                {"name": "beta",  "command": "beta-cmd"},
            ],
        }))
        result = dashboard_module.settings_mcps()
        names = [r["name"] for r in result["mcps"]]
        assert names == sorted(["alpha", "beta"])


# ─── /api/settings/hooks ────────────────────────────────────────────────


class TestHooksEndpoint:
    def test_returns_empty_when_settings_missing(self, dashboard_module, tmp_home):
        result = dashboard_module.settings_hooks()
        assert result["hooks"] == []

    def test_parses_full_hooks_block(self, dashboard_module, tmp_home):
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "/path/session-start.sh", "timeout": 5}]},
                ],
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": "/path/user-prompt.sh", "timeout": 10}]},
                ],
            },
        }))
        result = dashboard_module.settings_hooks()
        by_type = {r["hook"]: r for r in result["hooks"]}
        assert "SessionStart" in by_type
        assert "UserPromptSubmit" in by_type
        assert by_type["SessionStart"]["count"] == 1
        assert by_type["SessionStart"]["commands"][0]["timeout"] == 5

    def test_surfaces_hard_enforcement_flag(self, dashboard_module, tmp_home):
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({
            "hooks": {
                "hardEnforcement": True,
                "UserPromptSubmit": [],
            },
        }))
        result = dashboard_module.settings_hooks()
        assert result["hard_enforcement"] is True

    def test_corrupt_json_returns_empty(self, dashboard_module, tmp_home):
        settings_path = tmp_home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text("not-json{")
        result = dashboard_module.settings_hooks()
        assert result["hooks"] == []


# ─── /api/settings/plugins ──────────────────────────────────────────────


class TestPluginsEndpoint:
    def test_returns_empty_when_file_missing(self, dashboard_module, tmp_home):
        result = dashboard_module.settings_plugins()
        assert result["plugins"] == []
        assert result["total"] == 0

    def test_flattens_marketplace_keyed_entries(self, dashboard_module, tmp_home):
        plugins_path = tmp_home / ".claude" / "plugins" / "installed_plugins.json"
        plugins_path.parent.mkdir(parents=True)
        plugins_path.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "frontend-design@claude-plugins-official": [
                    {"scope": "user", "version": "1.0.0", "installedAt": "2026-05-24T12:00:00Z"},
                ],
                "claude-mem@thedotmack": [
                    {"scope": "user", "version": "10.6.2", "installedAt": "2026-03-26T19:48:33.661Z"},
                ],
            },
        }))
        result = dashboard_module.settings_plugins()
        assert result["total"] == 2
        names = {r["name"] for r in result["plugins"]}
        assert "frontend-design" in names
        assert "claude-mem" in names
        fd = next(r for r in result["plugins"] if r["name"] == "frontend-design")
        assert fd["marketplace"] == "claude-plugins-official"
        assert fd["version"] == "1.0.0"

    def test_handles_corrupt_json(self, dashboard_module, tmp_home):
        plugins_path = tmp_home / ".claude" / "plugins" / "installed_plugins.json"
        plugins_path.parent.mkdir(parents=True)
        plugins_path.write_text("not-json{")
        result = dashboard_module.settings_plugins()
        assert result["plugins"] == []
