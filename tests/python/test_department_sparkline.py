"""Tests for the department activity sparkline endpoint (PR97a v3.59.0)."""

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


def test_unknown_department_returns_error():
    api = _load_dashboard_api()
    res = api.department_activity_sparkline("definitely-not-real-zzz")
    assert "error" in res


def test_seeded_buckets_returned_for_known_dept():
    api = _load_dashboard_api()
    res_list = api.departments_list()
    if not res_list["departments"]:
        return
    dept = res_list["departments"][0]["department"]
    res = api.department_activity_sparkline(dept, days=14)
    assert "days" in res
    assert len(res["days"]) == 14
    assert res["period_days"] == 14


def test_caps_at_90_days():
    api = _load_dashboard_api()
    res_list = api.departments_list()
    if not res_list["departments"]:
        return
    dept = res_list["departments"][0]["department"]
    res = api.department_activity_sparkline(dept, days=999)
    assert res["period_days"] == 90
    assert len(res["days"]) == 90


def test_invalid_days_falls_back_to_30():
    api = _load_dashboard_api()
    res_list = api.departments_list()
    if not res_list["departments"]:
        return
    dept = res_list["departments"][0]["department"]
    res = api.department_activity_sparkline(dept, days="bogus")
    assert res["period_days"] == 30


def test_day_shape_and_sort_order():
    api = _load_dashboard_api()
    res_list = api.departments_list()
    if not res_list["departments"]:
        return
    dept = res_list["departments"][0]["department"]
    res = api.department_activity_sparkline(dept, days=10)
    dates = [d["date"] for d in res["days"]]
    assert dates == sorted(dates)
    for d in res["days"]:
        assert "date" in d
        assert "calls" in d
        assert "cost_usd" in d
        assert isinstance(d["calls"], int)
        assert d["calls"] >= 0
