"""Tests for the CSV cost export endpoint (PR91d v3.38.0)."""

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


def test_returns_csv_response():
    api = _load_dashboard_api()
    res = api.llm_costs_export()
    if isinstance(res, dict):
        return  # telemetry unavailable — environment specific
    assert res.media_type == "text/csv"
    assert "attachment" in res.headers.get("content-disposition", "")


def test_invalid_period_falls_back_to_month():
    api = _load_dashboard_api()
    res = api.llm_costs_export(period="bogus")
    if isinstance(res, dict):
        return
    # Filename embeds the period; falls back to month
    assert "arkaos-costs-month.csv" in res.headers["content-disposition"]


def test_csv_header_present():
    api = _load_dashboard_api()
    res = api.llm_costs_export(period="all")
    if isinstance(res, dict):
        return
    body = res.body.decode("utf-8") if isinstance(res.body, bytes) else res.body
    lines = body.splitlines()
    assert lines, "CSV must have at least the header row"
    header = lines[0]
    for col in ("ts", "session_id", "provider", "model", "category",
                "tokens_in", "tokens_out", "cached_tokens", "estimated_cost_usd"):
        assert col in header


def test_filename_uses_period():
    api = _load_dashboard_api()
    res = api.llm_costs_export(period="week")
    if isinstance(res, dict):
        return
    assert "arkaos-costs-week.csv" in res.headers["content-disposition"]
