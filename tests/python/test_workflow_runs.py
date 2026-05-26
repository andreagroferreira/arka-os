"""Tests for workflow runs endpoint (PR89b v3.28.0)."""

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


def test_unknown_workflow_returns_empty_runs():
    api = _load_dashboard_api()
    res = api.workflow_runs("nonexistent-workflow-zzzzz")
    assert res == {"runs": []}


def test_returns_runs_list():
    api = _load_dashboard_api()
    res = api.workflow_runs("any-workflow", limit=5)
    assert "runs" in res
    assert isinstance(res["runs"], list)


def test_limit_caps_results():
    api = _load_dashboard_api()
    res = api.workflow_runs("any-workflow", limit=0)
    assert res == {"runs": []}


def test_iso_duration_calculation():
    api = _load_dashboard_api()
    d = api._iso_duration_s(
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:01:30+00:00",
    )
    assert d == 90


def test_iso_duration_handles_empty_strings():
    api = _load_dashboard_api()
    assert api._iso_duration_s("", "2026-01-01T00:00:00+00:00") is None
    assert api._iso_duration_s("2026-01-01T00:00:00+00:00", "") is None


def test_iso_duration_handles_z_suffix():
    api = _load_dashboard_api()
    d = api._iso_duration_s(
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:30Z",
    )
    assert d == 30


def test_iso_duration_handles_malformed():
    api = _load_dashboard_api()
    assert api._iso_duration_s("not-a-date", "2026-01-01T00:00:00Z") is None
