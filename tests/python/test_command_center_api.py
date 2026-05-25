"""Tests for /api/overview/command-center + helpers (PR66 v2.83.0)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
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


# ─── _parse_descriptor ──────────────────────────────────────────────────


class TestParseDescriptor:
    def test_minimal_descriptor(self, dashboard_module, tmp_path):
        path = tmp_path / "proj.md"
        path.write_text("# proj\n\nbody\n")
        result = dashboard_module._parse_descriptor(path)
        assert result["name"] == "proj"
        assert result["stack"] == []
        assert result["status"] == "unknown"

    def test_full_frontmatter(self, dashboard_module, tmp_path):
        path = tmp_path / "acme.md"
        path.write_text(
            "---\nname: acme-supplier-sync\n"
            "path: /Users/foo/Work/acme-supplier-sync\n"
            "stack:\n  - nuxt\n  - typescript\n  - postgres\n"
            "status: active\necosystem: acme\n---\n\nbody\n",
            encoding="utf-8",
        )
        result = dashboard_module._parse_descriptor(path)
        assert result["name"] == "acme-supplier-sync"
        assert result["path"] == "/Users/foo/Work/acme-supplier-sync"
        assert result["stack"] == ["nuxt", "typescript", "postgres"]
        assert result["status"] == "active"
        assert result["ecosystem"] == "acme"

    def test_caps_stack_at_six(self, dashboard_module, tmp_path):
        stack = "\n".join(f"  - tech{i}" for i in range(20))
        path = tmp_path / "p.md"
        path.write_text(f"---\nname: p\nstack:\n{stack}\n---\nbody\n", encoding="utf-8")
        result = dashboard_module._parse_descriptor(path)
        assert len(result["stack"]) == 6

    def test_handles_scalar_stack(self, dashboard_module, tmp_path):
        """Some descriptors write stack as a single string, not a list."""
        path = tmp_path / "p.md"
        path.write_text("---\nname: p\nstack: laravel\n---\nbody\n", encoding="utf-8")
        result = dashboard_module._parse_descriptor(path)
        assert result["stack"] == ["laravel"]

    def test_handles_malformed_yaml(self, dashboard_module, tmp_path):
        """A broken YAML block must not raise; fields fall back to defaults."""
        path = tmp_path / "broken.md"
        path.write_text(
            "---\n  : invalid yaml because key is missing\n---\nbody\n",
            encoding="utf-8",
        )
        result = dashboard_module._parse_descriptor(path)
        # name falls back to file stem
        assert result["name"] == "broken"


# ─── _last_commit_days ──────────────────────────────────────────────────


class TestLastCommitDays:
    def test_returns_none_when_path_missing(self, dashboard_module):
        assert dashboard_module._last_commit_days("/no/such/dir") is None

    def test_returns_none_when_not_a_git_repo(self, dashboard_module, tmp_path):
        not_a_repo = tmp_path / "regular-dir"
        not_a_repo.mkdir()
        assert dashboard_module._last_commit_days(str(not_a_repo)) is None

    def test_returns_none_on_empty_string(self, dashboard_module):
        assert dashboard_module._last_commit_days("") is None


# ─── _recent_incidents ──────────────────────────────────────────────────


class TestRecentIncidents:
    def test_returns_empty_when_log_missing(self, dashboard_module, tmp_path, monkeypatch):
        # Point HOME at an empty dir so Path.home() / .arkaos / ... resolves
        # to a path that doesn't exist. _recent_incidents must handle that.
        monkeypatch.setenv("HOME", str(tmp_path))
        assert dashboard_module._recent_incidents() == []

    def test_filters_for_bypass_or_blocked(self, dashboard_module, tmp_path, monkeypatch):
        # Set up a fake telemetry log under a tmp HOME
        monkeypatch.setenv("HOME", str(tmp_path))
        log_path = tmp_path / ".arkaos" / "telemetry" / "enforcement.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"ts": "2026-05-25T10:00:00+00:00", "tool": "Edit",
             "allow": True, "bypass_used": False, "reason": "classifier-did-not-match"},
            {"ts": "2026-05-25T10:01:00+00:00", "tool": "Write",
             "allow": False, "bypass_used": False, "reason": "no-flow-marker"},
            {"ts": "2026-05-25T10:02:00+00:00", "tool": "Edit",
             "allow": True, "bypass_used": True, "reason": "ARKA_BYPASS_FLOW=1"},
        ]
        log_path.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8",
        )
        incidents = dashboard_module._recent_incidents(limit=10)
        # The 'classifier-did-not-match' row is filtered out
        kinds = [r["kind"] for r in incidents]
        assert "bypass" in kinds
        assert "blocked" in kinds
        assert len(incidents) == 2

    def test_caps_at_limit(self, dashboard_module, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        log_path = tmp_path / ".arkaos" / "telemetry" / "enforcement.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"ts": f"2026-05-25T10:{i:02}:00+00:00", "tool": "Edit",
             "allow": False, "bypass_used": False, "reason": "block"}
            for i in range(20)
        ]
        log_path.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8",
        )
        incidents = dashboard_module._recent_incidents(limit=5)
        assert len(incidents) == 5

    def test_skips_malformed_lines(self, dashboard_module, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        log_path = tmp_path / ".arkaos" / "telemetry" / "enforcement.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            'not-json\n'
            + json.dumps({"ts": "x", "allow": False, "tool": "Edit", "reason": "blocked"})
            + "\n",
            encoding="utf-8",
        )
        incidents = dashboard_module._recent_incidents()
        assert len(incidents) == 1


# ─── /api/overview/command-center ───────────────────────────────────────


class TestCommandCenterEndpoint:
    def test_returns_required_keys(self, dashboard_module, tmp_path, monkeypatch):
        """Smoke: every documented key appears in the payload."""
        monkeypatch.setenv("HOME", str(tmp_path))
        result = dashboard_module.overview_command_center()
        for key in (
            "greeting", "today_cost", "projects",
            "recent_incidents", "quick_actions",
        ):
            assert key in result, f"missing {key}"
        # Greeting shape
        for key in ("name", "role", "company", "language"):
            assert key in result["greeting"]
        # Today cost shape
        for key in (
            "total_usd", "call_count", "tokens_in",
            "tokens_out", "cache_hit_rate",
        ):
            assert key in result["today_cost"]
        # Quick actions has commands
        assert all("command" in a and "description" in a for a in result["quick_actions"])

    def test_greeting_reflects_profile(self, dashboard_module, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Seed profile
        profile_path = tmp_path / ".arkaos" / "profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps({
            "name": "Test User",
            "company": "ACME",
            "role": "founder",
            "language": "pt",
        }))
        result = dashboard_module.overview_command_center()
        assert result["greeting"]["name"] == "Test User"
        assert result["greeting"]["company"] == "ACME"
        assert result["greeting"]["role"] == "founder"
        assert result["greeting"]["language"] == "pt"

    def test_projects_empty_when_no_descriptors(self, dashboard_module, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        result = dashboard_module.overview_command_center()
        assert result["projects"] == []
