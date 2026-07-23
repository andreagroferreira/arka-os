"""Tests for /api/personas/usage (PR77 v2.95.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def _write_agent(tmp_path: Path, agent_id: str, linked: list[str] | None) -> Path:
    """Write a minimal agent YAML and return the path."""
    p = tmp_path / f"{agent_id}.yaml"
    data = {"id": agent_id, "name": agent_id, "department": "dev", "tier": 2}
    if linked is not None:
        data["linked_personas"] = linked
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


class TestPersonasUsage:
    def test_returns_empty_when_no_linked_personas(
        self, dashboard_module, tmp_path, monkeypatch,
    ):
        a1 = _write_agent(tmp_path, "agent-1", None)
        a2 = _write_agent(tmp_path, "agent-2", [])
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [
                {"id": "agent-1", "file": str(a1.relative_to(REPO_ROOT)) if str(a1).startswith(str(REPO_ROOT)) else None},
                {"id": "agent-2", "file": str(a2.relative_to(REPO_ROOT)) if str(a2).startswith(str(REPO_ROOT)) else None},
            ],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            monkeypatch.setattr(
                dashboard_module, "_load_agents",
                lambda: [
                    {"id": "agent-1", "file": "agent-1.yaml"},
                    {"id": "agent-2", "file": "agent-2.yaml"},
                ],
            )
            result = dashboard_module.personas_usage()
        assert result["by_persona"] == {}

    def test_counts_agents_linked_to_each_persona(
        self, dashboard_module, tmp_path, monkeypatch,
    ):
        _write_agent(tmp_path, "agent-1", ["alex-hormozi", "naval-ravikant"])
        _write_agent(tmp_path, "agent-2", ["alex-hormozi"])
        _write_agent(tmp_path, "agent-3", ["dan-martell"])
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [
                {"id": "agent-1", "file": "agent-1.yaml"},
                {"id": "agent-2", "file": "agent-2.yaml"},
                {"id": "agent-3", "file": "agent-3.yaml"},
            ],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            result = dashboard_module.personas_usage()
        assert result["by_persona"]["alex-hormozi"]["agent_count"] == 2
        assert set(result["by_persona"]["alex-hormozi"]["agent_ids"]) == {"agent-1", "agent-2"}
        assert result["by_persona"]["naval-ravikant"]["agent_count"] == 1
        assert result["by_persona"]["dan-martell"]["agent_count"] == 1

    def test_skips_agents_without_yaml(
        self, dashboard_module, tmp_path, monkeypatch,
    ):
        """An agent listed in the registry but whose YAML is missing
        on disk must not crash the loop."""
        _write_agent(tmp_path, "agent-1", ["alex"])
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [
                {"id": "agent-1", "file": "agent-1.yaml"},
                {"id": "agent-missing", "file": "no-such.yaml"},
            ],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            result = dashboard_module.personas_usage()
        assert result["by_persona"]["alex"]["agent_count"] == 1

    def test_skips_corrupt_yaml(self, dashboard_module, tmp_path, monkeypatch):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not-yaml{::", encoding="utf-8")
        _write_agent(tmp_path, "good", ["x"])
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [
                {"id": "good", "file": "good.yaml"},
                {"id": "bad",  "file": "bad.yaml"},
            ],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            result = dashboard_module.personas_usage()
        assert "x" in result["by_persona"]

    def test_ignores_non_list_linked_personas(
        self, dashboard_module, tmp_path, monkeypatch,
    ):
        weird = tmp_path / "weird.yaml"
        weird.write_text(yaml.safe_dump({"linked_personas": "not-a-list"}), encoding="utf-8")
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [{"id": "weird", "file": "weird.yaml"}],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            result = dashboard_module.personas_usage()
        assert result["by_persona"] == {}

    def test_ignores_non_string_persona_ids(
        self, dashboard_module, tmp_path, monkeypatch,
    ):
        weird = tmp_path / "weird.yaml"
        weird.write_text(yaml.safe_dump({
            "linked_personas": ["valid", 42, None, {"a": 1}, "also-valid"],
        }), encoding="utf-8")
        monkeypatch.setattr(
            dashboard_module, "_load_agents",
            lambda: [{"id": "weird", "file": "weird.yaml"}],
        )
        with patch.object(dashboard_module, "ARKAOS_ROOT", tmp_path):
            result = dashboard_module.personas_usage()
        assert set(result["by_persona"].keys()) == {"valid", "also-valid"}
