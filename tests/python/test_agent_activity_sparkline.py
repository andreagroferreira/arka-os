"""Tests for the agent activity sparkline endpoint (PR96d v3.58.0)."""

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


def test_unknown_agent_returns_error():
    api = _load_dashboard_api()
    res = api.agent_activity_sparkline("not-a-real-agent-zzzzz")
    assert "error" in res


def test_returns_days_seeded_with_zeros():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"], days=14)
    assert "days" in res
    assert len(res["days"]) == 14


def test_default_period_30_days():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"])
    assert res.get("period_days") == 30
    assert len(res["days"]) == 30


def test_caps_at_90_days():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"], days=500)
    assert res["period_days"] == 90
    assert len(res["days"]) == 90


def test_invalid_days_falls_back_to_default():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"], days="not-a-number")
    assert res["period_days"] == 30


def test_day_shape():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"], days=7)
    for d in res["days"]:
        assert "date" in d
        assert "calls" in d
        assert "cost_usd" in d
        assert isinstance(d["calls"], int)
        assert d["calls"] >= 0


def test_days_sorted_ascending():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_activity_sparkline(agents[0]["id"], days=10)
    dates = [d["date"] for d in res["days"]]
    assert dates == sorted(dates)
