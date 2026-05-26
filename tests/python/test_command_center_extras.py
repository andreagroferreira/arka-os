"""Tests for the extra command-center cards (PR84d v3.10.0)."""

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


def test_top_departments_returns_list():
    api = _load_dashboard_api()
    out = api._top_departments_by_cost(period="month", top_n=5)
    assert isinstance(out, list)
    assert len(out) <= 5
    for row in out:
        assert "department" in row
        assert "calls" in row
        assert isinstance(row["calls"], int)
        assert row["calls"] >= 0
        # cost_usd may be None when no cost is known
        if row["cost_usd"] is not None:
            assert isinstance(row["cost_usd"], float)


def test_top_departments_invalid_period_falls_back():
    api = _load_dashboard_api()
    out = api._top_departments_by_cost(period="bogus", top_n=5)
    assert isinstance(out, list)


def test_top_departments_respects_limit():
    api = _load_dashboard_api()
    out = api._top_departments_by_cost(period="month", top_n=2)
    assert len(out) <= 2


def test_recent_personas_returns_list():
    api = _load_dashboard_api()
    out = api._recent_personas(limit=5)
    assert isinstance(out, list)
    assert len(out) <= 5
    for row in out:
        assert "id" in row
        assert "name" in row
        assert "mbti" in row
        assert "source_store" in row


def test_recent_personas_respects_limit():
    api = _load_dashboard_api()
    out = api._recent_personas(limit=1)
    assert len(out) <= 1


def test_command_center_payload_has_new_keys():
    api = _load_dashboard_api()
    payload = api.overview_command_center()
    assert "top_departments_30d" in payload
    assert "recent_personas" in payload
    assert isinstance(payload["top_departments_30d"], list)
    assert isinstance(payload["recent_personas"], list)
