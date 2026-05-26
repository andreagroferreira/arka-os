"""Tests for the workflows scan endpoint (PR88b v3.24.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dashboard_api():
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_returns_workflows_list():
    api = _load_dashboard_api()
    res = api.workflows_list()
    assert "workflows" in res
    assert isinstance(res["workflows"], list)


def test_workflow_shape():
    api = _load_dashboard_api()
    res = api.workflows_list()
    if not res["workflows"]:
        return  # No workflows in this checkout — environment dependent
    w = res["workflows"][0]
    for key in (
        "id", "name", "description", "department", "tier",
        "command", "phases_count", "file", "content",
    ):
        assert key in w
    assert isinstance(w["phases_count"], int)
    assert isinstance(w["content"], str)
    assert w["file"].startswith("departments/")


def test_workflows_have_known_departments():
    api = _load_dashboard_api()
    res = api.workflows_list()
    if not res["workflows"]:
        return
    depts = {w["department"] for w in res["workflows"]}
    # All non-empty
    assert all(d for d in depts)


def test_phases_count_non_negative():
    api = _load_dashboard_api()
    res = api.workflows_list()
    for w in res["workflows"]:
        assert w["phases_count"] >= 0


def test_phases_summary_present():
    """PR91c — each workflow now ships a `phases` array of distilled stepper data."""
    api = _load_dashboard_api()
    res = api.workflows_list()
    if not res["workflows"]:
        return
    w = next((w for w in res["workflows"] if w["phases_count"] > 0), None)
    if not w:
        return
    assert "phases" in w
    assert isinstance(w["phases"], list)
    assert len(w["phases"]) == w["phases_count"]
    for ph in w["phases"]:
        assert "id" in ph
        assert "name" in ph
        assert "gate_type" in ph
        assert "agent_count" in ph
        assert isinstance(ph["agent_count"], int)


def test_summarise_phases_skips_non_dicts():
    api = _load_dashboard_api()
    out = api._summarise_phases(["not a dict", {"id": "x", "name": "X"}])
    assert len(out) == 1
    assert out[0]["id"] == "x"


def test_summarise_phases_captures_agent_ids():
    """PR93a — agent_ids surface as a string list."""
    api = _load_dashboard_api()
    out = api._summarise_phases([
        {
            "id": "ph1",
            "name": "Phase 1",
            "agents": [
                {"agent_id": "tomas-strategy"},
                {"agent_id": "marta-cqo"},
                {"no_agent_id": True},  # ignored
            ],
        },
    ])
    assert out[0]["agent_ids"] == ["tomas-strategy", "marta-cqo"]
    assert out[0]["agent_count"] == 2


def test_summarise_phases_handles_missing_keys():
    api = _load_dashboard_api()
    out = api._summarise_phases([{}])
    assert out[0]["id"] == ""
    assert out[0]["agent_count"] == 0
    assert out[0]["gate_type"] == ""


def test_content_is_yaml_string():
    api = _load_dashboard_api()
    res = api.workflows_list()
    if not res["workflows"]:
        return
    w = res["workflows"][0]
    # YAML headers tend to have at least one of these tokens
    assert any(token in w["content"] for token in ("id:", "name:", "phases:"))
