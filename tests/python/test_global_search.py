"""Tests for the global search endpoint (PR85d v3.14.0)."""

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


def test_empty_query_returns_empty():
    api = _load_dashboard_api()
    res = api.global_search(q="")
    assert res == {"results": []}


def test_whitespace_only_query_returns_empty():
    api = _load_dashboard_api()
    res = api.global_search(q="   ")
    assert res == {"results": []}


def test_result_shape():
    api = _load_dashboard_api()
    # "dev" should match the dev department + any dev agents in the registry
    res = api.global_search(q="dev")
    assert "results" in res
    assert isinstance(res["results"], list)
    for row in res["results"]:
        assert "kind" in row
        assert "id" in row
        assert "label" in row
        assert "sublabel" in row
        assert "to" in row
        assert row["kind"] in ("agent", "persona", "department", "command")


def test_limit_caps_results():
    api = _load_dashboard_api()
    # A very broad query; results capped at 5
    res = api.global_search(q="a", limit=5)
    assert len(res["results"]) <= 5


def test_department_results_present_for_known_dept():
    api = _load_dashboard_api()
    res = api.global_search(q="finance")
    kinds = {r["kind"] for r in res["results"]}
    # Either matches a finance dept or finance-tagged agent — both are
    # legitimate, but at least one should hit.
    assert kinds, "expected at least one match for 'finance'"


def test_case_insensitive_search():
    api = _load_dashboard_api()
    lower = api.global_search(q="dev")
    upper = api.global_search(q="DEV")
    assert len(lower["results"]) == len(upper["results"])
