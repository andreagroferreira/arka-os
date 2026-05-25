"""Tests for the /api/llm-costs and /api/llm-costs/trend endpoints (PR65)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    """Load scripts/dashboard-api.py as an importable module."""
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_telemetry(tmp_path, monkeypatch):
    """Point the cost-telemetry reader at a fresh JSONL we control."""
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    return path


def _row(
    ts: datetime,
    *,
    tokens_in: int = 100,
    tokens_out: int = 50,
    cost: float | None = 0.01,
    category: str | None = None,
    provider: str = "anthropic",
    model: str = "claude-opus-4-7",
) -> dict:
    row = {
        "ts": ts.isoformat(),
        "session_id": "s",
        "provider": provider,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cached_tokens": 0,
        "estimated_cost_usd": cost,
    }
    if category is not None:
        row["category"] = category
    return row


def _seed(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8",
    )


# ─── /api/llm-costs ──────────────────────────────────────────────────────


class TestLlmCostsEndpoint:
    def test_rejects_invalid_period(self, dashboard_module):
        result = dashboard_module.llm_costs(period="invalid")
        assert "error" in result
        assert "period" in result["error"]

    def test_returns_summary_with_pr47_fields(self, dashboard_module, tmp_telemetry):
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="skill:arka", cost=1.0),
            _row(now, category="subagent:dev", cost=0.5),
            _row(now, cost=0.25),  # no category → "" bucket
        ])
        result = dashboard_module.llm_costs(period="all")
        # Required PR47 shape
        for key in (
            "period", "total_cost_usd", "total_tokens_in", "total_tokens_out",
            "total_cached_tokens", "cache_hit_rate", "call_count",
            "by_provider", "by_model", "by_category", "by_session",
            "advisories", "corrupt_line_count",
        ):
            assert key in result, f"missing key {key}"
        assert result["call_count"] == 3
        assert result["total_cost_usd"] == pytest.approx(1.75, abs=1e-6)
        assert "skill:arka" in result["by_category"]
        assert "subagent:dev" in result["by_category"]
        assert "" in result["by_category"]

    def test_accepts_all_valid_periods(self, dashboard_module, tmp_telemetry):
        _seed(tmp_telemetry, [])
        for p in ("today", "week", "month", "all"):
            result = dashboard_module.llm_costs(period=p)
            assert "error" not in result
            assert result["period"] == p


# ─── /api/llm-costs/trend ────────────────────────────────────────────────


class TestLlmCostsTrend:
    def test_returns_one_bucket_per_day(self, dashboard_module, tmp_telemetry):
        _seed(tmp_telemetry, [])
        result = dashboard_module.llm_costs_trend(days=7)
        assert len(result["days"]) == 7
        assert result["period_days"] == 7

    def test_caps_days_at_90(self, dashboard_module, tmp_telemetry):
        _seed(tmp_telemetry, [])
        result = dashboard_module.llm_costs_trend(days=500)
        assert result["period_days"] == 90
        assert len(result["days"]) == 90

    def test_floors_days_at_1(self, dashboard_module, tmp_telemetry):
        _seed(tmp_telemetry, [])
        result = dashboard_module.llm_costs_trend(days=0)
        assert result["period_days"] == 1
        assert len(result["days"]) == 1

    def test_aggregates_per_day(self, dashboard_module, tmp_telemetry):
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        _seed(tmp_telemetry, [
            _row(today, cost=0.10, tokens_in=100, tokens_out=20),
            _row(today, cost=0.05, tokens_in=50, tokens_out=10),
            _row(yesterday, cost=0.20, tokens_in=200, tokens_out=40),
        ])
        result = dashboard_module.llm_costs_trend(days=7)
        today_bucket = next(b for b in result["days"] if b["date"] == today.date().isoformat())
        yest_bucket = next(b for b in result["days"] if b["date"] == yesterday.date().isoformat())
        assert today_bucket["call_count"] == 2
        assert today_bucket["tokens_in"] == 150
        assert today_bucket["tokens_out"] == 30
        assert today_bucket["cost_usd"] == pytest.approx(0.15, abs=1e-6)
        assert yest_bucket["call_count"] == 1
        assert yest_bucket["cost_usd"] == pytest.approx(0.20, abs=1e-6)

    def test_missing_cost_yields_null(self, dashboard_module, tmp_telemetry):
        today = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(today, cost=None, tokens_in=100, tokens_out=20),
        ])
        result = dashboard_module.llm_costs_trend(days=1)
        today_bucket = result["days"][0]
        assert today_bucket["cost_usd"] is None
        assert today_bucket["call_count"] == 1
        assert today_bucket["tokens_in"] == 100

    def test_zero_buckets_for_quiet_days(self, dashboard_module, tmp_telemetry):
        """Days with no telemetry must still appear, zeroed out."""
        _seed(tmp_telemetry, [])
        result = dashboard_module.llm_costs_trend(days=5)
        assert len(result["days"]) == 5
        for b in result["days"]:
            assert b["call_count"] == 0
            assert b["tokens_in"] == 0
            assert b["cost_usd"] is None  # cost_known never flipped

    def test_ignores_malformed_ts(self, dashboard_module, tmp_telemetry):
        today = datetime.now(timezone.utc)
        rows = [
            _row(today, cost=0.10),
            {"ts": "garbage", "tokens_in": 999, "estimated_cost_usd": 99.9},
        ]
        _seed(tmp_telemetry, rows)
        result = dashboard_module.llm_costs_trend(days=1)
        assert result["days"][0]["call_count"] == 1
        assert result["days"][0]["cost_usd"] == pytest.approx(0.10, abs=1e-6)

    def test_ignores_rows_older_than_window(self, dashboard_module, tmp_telemetry):
        today = datetime.now(timezone.utc)
        far_past = today - timedelta(days=30)
        _seed(tmp_telemetry, [
            _row(today, cost=0.10),
            _row(far_past, cost=99.99),  # outside the 7-day window
        ])
        result = dashboard_module.llm_costs_trend(days=7)
        total = sum(b["call_count"] for b in result["days"])
        assert total == 1  # only today's row counted
