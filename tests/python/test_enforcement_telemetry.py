"""Tests for core.governance.enforcement_telemetry (PR19 v2.41.0).

Summarizer over ~/.arkaos/telemetry/enforcement.jsonl. Mirrors the
llm_cost_telemetry pattern used by /arka costs — same period vocabulary,
same tolerance for malformed lines, same zero-division safety.

TDD red phase: all imports/assertions fail before implementation exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.governance.enforcement_telemetry import (
    EnforcementSummary,
    summarise,
)


# ─── Fixtures ───────────────────────────────────────────────────────────


def _entry(
    *,
    ts: datetime,
    tool: str = "Edit",
    allow: bool = True,
    reason: str = "classifier-did-not-match",
    bypass_used: bool = False,
    session_id: str = "sess-1",
) -> dict:
    return {
        "ts": ts.isoformat(),
        "session_id": session_id,
        "tool": tool,
        "cwd": "/tmp/test",
        "allow": allow,
        "reason": reason,
        "marker_found": None,
        "phase_observed": None,
        "bypass_used": bypass_used,
    }


@pytest.fixture()
def tmp_telemetry(tmp_path: Path) -> Path:
    return tmp_path / "enforcement.jsonl"


def _write(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e) for e in entries) + ("\n" if entries else ""),
        encoding="utf-8",
    )


# ─── Empty + malformed input ────────────────────────────────────────────


class TestRobustness:
    def test_missing_file_returns_zero_summary(self, tmp_path: Path):
        path = tmp_path / "does-not-exist.jsonl"
        result = summarise("all", path=path)
        assert isinstance(result, EnforcementSummary)
        assert result.total_calls == 0
        assert result.blocked_calls == 0
        assert result.block_rate == 0.0

    def test_empty_file_returns_zero_summary(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 0
        assert result.block_rate == 0.0

    def test_malformed_lines_skipped_no_crash(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        path = tmp_telemetry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "this is not json\n"
            + json.dumps(_entry(ts=now)) + "\n"
            + "{partial json\n"
            + json.dumps(_entry(ts=now, allow=False, reason="no-flow-marker-in-last-6")) + "\n",
            encoding="utf-8",
        )
        result = summarise("all", path=path)
        assert result.total_calls == 2  # two valid entries
        assert result.blocked_calls == 1

    def test_zero_total_zero_block_rate(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        # 0/0 must be 0.0, never raise
        assert result.block_rate == 0.0


# ─── Counting + block_rate ──────────────────────────────────────────────


class TestCounting:
    def test_block_rate_basic(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now, allow=True),
            _entry(ts=now, allow=True),
            _entry(ts=now, allow=True),
            _entry(ts=now, allow=False, reason="no-flow-marker-in-last-6"),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 4
        assert result.blocked_calls == 1
        assert result.block_rate == 0.25

    def test_bypass_counted_separately(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now, allow=True, reason="env-bypass", bypass_used=True),
            _entry(ts=now, allow=True, reason="env-bypass", bypass_used=True),
            _entry(ts=now, allow=True),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.bypass_used == 2
        assert result.blocked_calls == 0


# ─── Period filtering ───────────────────────────────────────────────────


class TestPeriod:
    def test_today_excludes_yesterday(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1, hours=2)
        _write(tmp_telemetry, [
            _entry(ts=yesterday, allow=False, reason="no-flow-marker"),
            _entry(ts=now, allow=False, reason="no-flow-marker"),
        ])
        result = summarise("today", path=tmp_telemetry)
        assert result.total_calls == 1
        assert result.blocked_calls == 1

    def test_week_includes_last_seven_days(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now - timedelta(days=5)),
            _entry(ts=now - timedelta(days=10)),  # outside week
        ])
        result = summarise("week", path=tmp_telemetry)
        assert result.total_calls == 1

    def test_all_returns_everything(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now - timedelta(days=60)),
            _entry(ts=now - timedelta(days=2)),
            _entry(ts=now),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 3

    def test_invalid_period_raises(self, tmp_telemetry: Path):
        with pytest.raises(ValueError):
            summarise("yesterday-ish", path=tmp_telemetry)


# ─── Top blocked tools + reasons ────────────────────────────────────────


class TestTopAggregations:
    def test_top_blocked_tools_sorted_descending(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now, allow=False, tool="Edit"),
            _entry(ts=now, allow=False, tool="Edit"),
            _entry(ts=now, allow=False, tool="Edit"),
            _entry(ts=now, allow=False, tool="Write"),
            _entry(ts=now, allow=False, tool="Write"),
            _entry(ts=now, allow=False, tool="Task"),
            _entry(ts=now, allow=True, tool="Read"),  # allowed → not counted
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.top_blocked_tools[0] == ("Edit", 3)
        assert result.top_blocked_tools[1] == ("Write", 2)
        assert result.top_blocked_tools[2] == ("Task", 1)
        # Read NOT in top_blocked because it was allowed
        assert all(t != "Read" for t, _ in result.top_blocked_tools)

    def test_top_block_reasons_sorted_descending(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now, allow=False, reason="no-flow-marker-in-last-6"),
            _entry(ts=now, allow=False, reason="no-flow-marker-in-last-6"),
            _entry(ts=now, allow=False, reason="bash-effect-unknown"),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.top_block_reasons[0][0] == "no-flow-marker-in-last-6"
        assert result.top_block_reasons[0][1] == 2

    def test_empty_top_lists_on_no_blocks(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(ts=now, allow=True),
            _entry(ts=now, allow=True),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.top_blocked_tools == []
        assert result.top_block_reasons == []


# ─── Return shape contract ──────────────────────────────────────────────


class TestSummaryShape:
    def test_summary_has_required_fields(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        for field in (
            "period", "total_calls", "blocked_calls", "block_rate",
            "bypass_used", "top_blocked_tools", "top_block_reasons",
        ):
            assert hasattr(result, field), f"missing field: {field}"

    def test_period_field_echoes_input(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        for period in ("today", "week", "month", "all"):
            result = summarise(period, path=tmp_telemetry)
            assert result.period == period
