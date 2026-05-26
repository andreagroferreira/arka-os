"""Tests for the persona usage timeline endpoint (PR97b v3.60.0)."""

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


def test_unknown_persona_returns_empty_timeline():
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("never-linked-by-anyone")
    assert "weeks" in res
    assert res["total_agents"] == 0
    assert len(res["weeks"]) == res["period_weeks"]


def test_default_weeks_12():
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("any-id-here")
    assert res["period_weeks"] == 12
    assert len(res["weeks"]) == 12


def test_caps_at_52_weeks():
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("any-id-here", weeks=999)
    assert res["period_weeks"] == 52
    assert len(res["weeks"]) == 52


def test_invalid_weeks_falls_back():
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("any-id-here", weeks="bogus")
    assert res["period_weeks"] == 12


def test_week_shape_and_sort_order():
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("any-id-here", weeks=8)
    dates = [w["week_start"] for w in res["weeks"]]
    assert dates == sorted(dates)
    for w in res["weeks"]:
        assert "week_start" in w
        assert "count" in w
        assert isinstance(w["count"], int)
        assert w["count"] >= 0


def test_total_agents_matches_sum_when_within_window():
    """Sum of bucket counts == total_agents only if every linking agent
    was modified within `weeks`. We can't guarantee that, but the sum
    must be <= total_agents."""
    api = _load_dashboard_api()
    res = api.persona_usage_timeline("any-id-here", weeks=52)
    bucket_sum = sum(w["count"] for w in res["weeks"])
    assert bucket_sum <= res["total_agents"]
