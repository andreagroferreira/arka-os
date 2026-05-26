"""Tests for the agents-suggestions endpoint (PR91a v3.35.0)."""

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
    res = api.agents_suggestions()
    assert "suggestions" in res
    assert "total_gaps" in res
    assert isinstance(res["suggestions"], list)
    assert isinstance(res["total_gaps"], int)


def test_suggestion_shape():
    api = _load_dashboard_api()
    res = api.agents_suggestions(limit=20)
    for s in res["suggestions"]:
        assert "department" in s
        assert "reason" in s
        assert "recommended_tier" in s
        assert "severity" in s
        assert s["severity"] in ("high", "medium")
        assert s["recommended_tier"] in (1, 2)


def test_limit_truncates():
    api = _load_dashboard_api()
    res = api.agents_suggestions(limit=2)
    assert len(res["suggestions"]) <= 2


def test_total_gaps_is_full_count():
    api = _load_dashboard_api()
    res_small = api.agents_suggestions(limit=1)
    res_full = api.agents_suggestions(limit=20)
    assert res_small["total_gaps"] == res_full["total_gaps"]


def test_high_severity_means_empty_dept():
    api = _load_dashboard_api()
    res = api.agents_suggestions(limit=20)
    for s in res["suggestions"]:
        if s["severity"] == "high":
            assert "empty" in s["reason"].lower() or "no agents" in s["reason"].lower()


def test_zero_limit_returns_empty_list():
    api = _load_dashboard_api()
    res = api.agents_suggestions(limit=0)
    assert res["suggestions"] == []


def test_known_departments_constant_has_16_entries():
    api = _load_dashboard_api()
    assert len(api._KNOWN_DEPARTMENTS) == 16
