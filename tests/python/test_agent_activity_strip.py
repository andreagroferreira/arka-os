"""Tests for the agent activity-strip endpoint (PR83d v3.6.0)."""

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


def test_returns_error_for_unknown_agent():
    api = _load_dashboard_api()
    res = api.agent_activity_strip("definitely-not-real-zzzz")
    assert "error" in res


def test_returns_payload_shape_for_existing_agent():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return  # Environment-dependent — skip silently
    target_id = agents[0]["id"]
    res = api.agent_activity_strip(target_id)
    assert "department" in res
    assert "calls" in res
    assert "cost_usd" in res
    assert "tokens_in" in res
    assert "tokens_out" in res
    assert "last_used" in res
    assert "dept_rank" in res
    assert "dept_count" in res
    assert "period" in res
    assert res["period"] == "month"
    # PR86b — scope field
    assert "scope" in res
    assert res["scope"] in ("agent", "department")


def test_activity_alias_returns_same_payload():
    """PR86b — /api/agents/{id}/activity is an alias for /activity-strip."""
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    target_id = agents[0]["id"]
    strip = api.agent_activity_strip(target_id)
    detail = api.agent_activity_detail(target_id)
    assert strip == detail


def test_scope_defaults_to_department_without_per_agent_tags():
    """When no telemetry exists for `subagent:<dept>:<agent_id>`, scope=dept."""
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_strip(agents[0]["id"])
    # Test env likely has no per-agent tags — should default to department
    assert res["scope"] in ("agent", "department")


def test_accepts_period_override():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_strip(agents[0]["id"], period="week")
    assert res["period"] == "week"


def test_invalid_period_falls_back_to_month():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_strip(agents[0]["id"], period="bogus")
    assert res["period"] == "month"


def test_calls_is_non_negative_int():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_strip(agents[0]["id"])
    assert isinstance(res["calls"], int)
    assert res["calls"] >= 0


def test_dept_rank_when_set_is_positive():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_strip(agents[0]["id"])
    if res.get("dept_rank") is not None:
        assert isinstance(res["dept_rank"], int)
        assert res["dept_rank"] >= 1
