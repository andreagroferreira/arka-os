"""Tests for the departments endpoints (PR89a v3.27.0)."""

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


def test_list_returns_payload_shape():
    api = _load_dashboard_api()
    res = api.departments_list()
    assert "departments" in res
    assert "total" in res
    assert isinstance(res["departments"], list)
    assert res["total"] == len(res["departments"])


def test_list_rows_have_required_fields():
    api = _load_dashboard_api()
    res = api.departments_list()
    if not res["departments"]:
        return
    row = res["departments"][0]
    for key in ("department", "agent_count", "tier_counts", "calls_30d", "cost_usd_30d"):
        assert key in row
    assert isinstance(row["agent_count"], int)
    assert row["agent_count"] >= 1
    assert set(row["tier_counts"].keys()) >= {"0", "1", "2", "3"}


def test_list_sorted_alphabetically():
    api = _load_dashboard_api()
    res = api.departments_list()
    names = [r["department"] for r in res["departments"]]
    assert names == sorted(names)


def test_detail_unknown_returns_error():
    api = _load_dashboard_api()
    res = api.department_detail("does-not-exist-zzzz")
    assert "error" in res


def test_detail_returns_agent_list():
    api = _load_dashboard_api()
    res = api.departments_list()
    if not res["departments"]:
        return
    dept = res["departments"][0]["department"]
    detail = api.department_detail(dept)
    assert detail["department"] == dept
    assert isinstance(detail["agents"], list)
    assert len(detail["agents"]) >= 1
    a = detail["agents"][0]
    for key in ("id", "name", "role", "tier"):
        assert key in a


def test_detail_includes_workflows():
    api = _load_dashboard_api()
    res = api.departments_list()
    if not res["departments"]:
        return
    dept = res["departments"][0]["department"]
    detail = api.department_detail(dept)
    assert "workflows" in detail
    assert isinstance(detail["workflows"], list)


def test_detail_cost_fields_present():
    api = _load_dashboard_api()
    res = api.departments_list()
    if not res["departments"]:
        return
    dept = res["departments"][0]["department"]
    detail = api.department_detail(dept)
    assert "calls_30d" in detail
    assert "cost_usd_30d" in detail
    assert isinstance(detail["calls_30d"], int)
