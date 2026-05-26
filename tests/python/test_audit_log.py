"""Tests for the audit log endpoint (PR90d v3.34.0)."""

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
    res = api.audit_log()
    assert "events" in res
    assert "total" in res
    assert isinstance(res["events"], list)
    assert isinstance(res["total"], int)


def test_default_limit_safe_when_no_log():
    api = _load_dashboard_api()
    res = api.audit_log(limit=100)
    assert res["total"] <= 100


def test_zero_limit_returns_empty():
    api = _load_dashboard_api()
    res = api.audit_log(limit=0)
    assert res == {"events": [], "total": 0}


def test_unknown_kind_returns_no_matches():
    api = _load_dashboard_api()
    res = api.audit_log(kind="never-going-to-match")
    assert res["events"] == []


def test_event_shape_has_kind():
    api = _load_dashboard_api()
    res = api.audit_log()
    for ev in res["events"]:
        assert ev["kind"] in ("bypass", "blocked")
        assert "ts" in ev
        assert "tool" in ev
        assert "reason" in ev


def test_kind_filter_only_returns_matching():
    api = _load_dashboard_api()
    res = api.audit_log(kind="bypass")
    for ev in res["events"]:
        assert ev["kind"] == "bypass"


def test_limit_capped_at_500():
    api = _load_dashboard_api()
    res = api.audit_log(limit=10_000)
    assert res["total"] <= 500
