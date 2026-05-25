"""Tests for the /api/agents/activity endpoint (PR69 v2.86.0)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_telemetry(tmp_path, monkeypatch):
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    return path


def _row(
    ts: datetime,
    *,
    category: str | None = None,
    tokens_in: int = 100,
    tokens_out: int = 20,
    cost: float | None = 0.01,
) -> dict:
    row = {
        "ts": ts.isoformat(),
        "session_id": "s",
        "provider": "anthropic",
        "model": "claude-opus-4-7",
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


class TestAgentsActivity:
    def test_returns_empty_when_no_telemetry(self, dashboard_module, tmp_telemetry):
        _seed(tmp_telemetry, [])
        result = dashboard_module.agents_activity(period="week")
        assert result["by_department"] == {}
        assert result["period"] == "week"

    def test_groups_subagent_categories_by_department(
        self, dashboard_module, tmp_telemetry,
    ):
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:dev", tokens_in=100, cost=0.10),
            _row(now, category="subagent:dev", tokens_in=200, cost=0.20),
            _row(now, category="subagent:brand", tokens_in=50, cost=0.05),
        ])
        result = dashboard_module.agents_activity(period="all")
        assert "dev" in result["by_department"]
        assert "brand" in result["by_department"]
        assert result["by_department"]["dev"]["call_count"] == 2
        assert result["by_department"]["dev"]["total_cost_usd"] == pytest.approx(0.30, abs=1e-6)
        assert result["by_department"]["brand"]["call_count"] == 1

    def test_ignores_non_subagent_categories(
        self, dashboard_module, tmp_telemetry,
    ):
        """Skill/plugin/mcp categories must not pollute the agent activity view."""
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:dev", tokens_in=100, cost=0.10),
            _row(now, category="skill:arka-spec", tokens_in=200, cost=0.50),
            _row(now, category="plugin:frontend-design", tokens_in=50),
            _row(now, category="mcp:obsidian", tokens_in=10),
            _row(now, category="", tokens_in=999),  # base bucket — also ignored
        ])
        result = dashboard_module.agents_activity(period="all")
        assert set(result["by_department"].keys()) == {"dev"}
        assert result["by_department"]["dev"]["call_count"] == 1

    def test_unknown_after_subagent_prefix(self, dashboard_module, tmp_telemetry):
        """`subagent:` alone (no dept) should still bucket under 'unknown'
        so the data isn't silently lost."""
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:", tokens_in=100, cost=0.10),
        ])
        result = dashboard_module.agents_activity(period="all")
        assert "unknown" in result["by_department"]
        assert result["by_department"]["unknown"]["call_count"] == 1

    def test_invalid_period_falls_back_to_week(
        self, dashboard_module, tmp_telemetry,
    ):
        _seed(tmp_telemetry, [])
        result = dashboard_module.agents_activity(period="centuries")
        assert result["period"] == "week"

    def test_cost_null_when_no_row_has_known_cost(
        self, dashboard_module, tmp_telemetry,
    ):
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:dev", cost=None),
            _row(now, category="subagent:dev", cost=None),
        ])
        result = dashboard_module.agents_activity(period="all")
        assert result["by_department"]["dev"]["total_cost_usd"] is None
        assert result["by_department"]["dev"]["call_count"] == 2

    def test_partial_cost_still_aggregates_known_rows(
        self, dashboard_module, tmp_telemetry,
    ):
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:dev", cost=0.10),
            _row(now, category="subagent:dev", cost=None),  # unknown
        ])
        result = dashboard_module.agents_activity(period="all")
        # One row knows cost; the bucket reports the known total only.
        assert result["by_department"]["dev"]["total_cost_usd"] == pytest.approx(0.10, abs=1e-6)
        assert result["by_department"]["dev"]["call_count"] == 2

    def test_tokens_aggregate_correctly(
        self, dashboard_module, tmp_telemetry,
    ):
        now = datetime.now(timezone.utc)
        _seed(tmp_telemetry, [
            _row(now, category="subagent:dev", tokens_in=100, tokens_out=50),
            _row(now, category="subagent:dev", tokens_in=200, tokens_out=80),
        ])
        result = dashboard_module.agents_activity(period="all")
        assert result["by_department"]["dev"]["total_tokens_in"] == 300
        assert result["by_department"]["dev"]["total_tokens_out"] == 130
