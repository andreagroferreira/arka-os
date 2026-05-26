"""Tests for the sidebar-stats endpoint (PR87d v3.22.0)."""

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


def test_returns_payload_shape():
    api = _load_dashboard_api()
    res = api.sidebar_stats()
    assert "agents" in res
    assert "personas" in res
    assert "departments" in res
    assert "today_cost_usd" in res
    assert "today_calls" in res


def test_counts_are_non_negative_ints():
    api = _load_dashboard_api()
    res = api.sidebar_stats()
    assert isinstance(res["agents"], int) and res["agents"] >= 0
    assert isinstance(res["personas"], int) and res["personas"] >= 0
    assert isinstance(res["departments"], int) and res["departments"] >= 0
    assert isinstance(res["today_calls"], int) and res["today_calls"] >= 0


def test_today_cost_is_float_or_none():
    api = _load_dashboard_api()
    res = api.sidebar_stats()
    if res["today_cost_usd"] is not None:
        assert isinstance(res["today_cost_usd"], float)
        assert res["today_cost_usd"] >= 0
