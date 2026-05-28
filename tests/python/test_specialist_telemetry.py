"""Tests for core.governance.specialist_telemetry (PR1 Squad Intelligence).

Summariser over ~/.arkaos/telemetry/specialist-dispatch.jsonl. Mirrors
the enforcement_telemetry test pattern — same period vocabulary, same
tolerance for malformed lines, same zero-division safety.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.governance.specialist_telemetry import (
    SpecialistSummary,
    summarise,
)


# ─── Fixtures ───────────────────────────────────────────────────────────


def _entry(
    *,
    ts: datetime,
    tool: str = "Write",
    allow: bool = True,
    reason: str = "owner-match:frontend-dev",
    current_persona: str | None = "frontend-dev",
    required_owners: list[str] | None = None,
    bypass_used: bool = False,
    bypass_reason: str | None = None,
    session_id: str = "sess-1",
) -> dict:
    return {
        "ts": ts.isoformat(),
        "session_id": session_id,
        "tool": tool,
        "cwd": "/tmp/test",
        "target_file": "/tmp/test/app.vue",
        "allow": allow,
        "reason": reason,
        "current_persona": current_persona,
        "required_owners": required_owners or [],
        "marker_found": "routing",
        "bypass_used": bypass_used,
        "bypass_reason": bypass_reason,
    }


@pytest.fixture()
def tmp_telemetry(tmp_path: Path) -> Path:
    return tmp_path / "specialist-dispatch.jsonl"


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
        assert isinstance(result, SpecialistSummary)
        assert result.total_calls == 0
        assert result.blocked_calls == 0
        assert result.block_rate == 0.0
        assert result.bypass_used == 0

    def test_empty_file_returns_zero_summary(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 0
        assert result.block_rate == 0.0

    def test_malformed_json_line_counts_as_corrupt(self, tmp_telemetry: Path):
        valid = _entry(ts=datetime.now(timezone.utc))
        tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
        tmp_telemetry.write_text(
            json.dumps(valid) + "\n{not valid json}\n",
            encoding="utf-8",
        )
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 1
        assert result.corrupt_line_count == 1

    def test_malformed_timestamp_counts_as_corrupt(
        self, tmp_telemetry: Path
    ):
        good = _entry(ts=datetime.now(timezone.utc))
        bad = dict(good)
        bad["ts"] = "not-an-iso-date"
        _write(tmp_telemetry, [good, bad])
        # Corrupt timestamps only matter when a cutoff is in effect.
        result = summarise("today", path=tmp_telemetry)
        assert result.corrupt_line_count == 1

    def test_blank_lines_skipped(self, tmp_telemetry: Path):
        valid = _entry(ts=datetime.now(timezone.utc))
        tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
        tmp_telemetry.write_text(
            "\n\n" + json.dumps(valid) + "\n\n",
            encoding="utf-8",
        )
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 1


# ─── Period filters ─────────────────────────────────────────────────────


class TestPeriods:
    def test_invalid_period_raises(self, tmp_telemetry: Path):
        with pytest.raises(ValueError, match="invalid period"):
            summarise("yesterday", path=tmp_telemetry)

    def test_today_filters_older_entries(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=2)
        fresh = _entry(ts=now)
        stale = _entry(ts=old, session_id="old-1")
        _write(tmp_telemetry, [stale, fresh])
        result = summarise("today", path=tmp_telemetry)
        assert result.total_calls == 1

    def test_week_includes_six_day_old_entry(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=6, hours=12)
        ancient = now - timedelta(days=10)
        _write(
            tmp_telemetry,
            [_entry(ts=recent), _entry(ts=ancient)],
        )
        result = summarise("week", path=tmp_telemetry)
        assert result.total_calls == 1

    def test_month_includes_29_day_old_entry(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(
            tmp_telemetry,
            [_entry(ts=now - timedelta(days=29))],
        )
        result = summarise("month", path=tmp_telemetry)
        assert result.total_calls == 1

    def test_all_period_includes_ancient_entry(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(
            tmp_telemetry,
            [_entry(ts=now - timedelta(days=365 * 2))],
        )
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 1


# ─── Aggregation logic ─────────────────────────────────────────────────


class TestAggregation:
    def test_block_rate_zero_when_no_blocks(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [_entry(ts=now), _entry(ts=now)])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 2
        assert result.blocked_calls == 0
        assert result.block_rate == 0.0

    def test_block_rate_calculated(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        allowed = _entry(ts=now)
        blocked = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked:paulo-not-in-[frontend-dev]",
            current_persona="paulo",
            required_owners=["frontend-dev"],
        )
        _write(tmp_telemetry, [allowed, blocked, blocked])
        result = summarise("all", path=tmp_telemetry)
        assert result.total_calls == 3
        assert result.blocked_calls == 2
        assert result.block_rate == pytest.approx(2 / 3)

    def test_bypass_counter(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        bypass = _entry(
            ts=now,
            allow=True,
            reason="bypass-with-reason",
            current_persona="paulo",
            required_owners=["frontend-dev"],
            bypass_used=True,
            bypass_reason="hotfix urgent",
        )
        _write(tmp_telemetry, [bypass, bypass, _entry(ts=now)])
        result = summarise("all", path=tmp_telemetry)
        assert result.bypass_used == 2

    def test_top_blocked_personas(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        paulo_block = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked",
            current_persona="paulo",
            required_owners=["frontend-dev"],
        )
        ines_block = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked",
            current_persona="ines",
            required_owners=["senior-dev"],
        )
        _write(
            tmp_telemetry,
            [paulo_block, paulo_block, paulo_block, ines_block],
        )
        result = summarise("all", path=tmp_telemetry)
        personas = dict(result.top_blocked_personas)
        assert personas["paulo"] == 3
        assert personas["ines"] == 1
        assert result.top_blocked_personas[0][0] == "paulo"

    def test_top_owners_required(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        front_block = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked",
            current_persona="paulo",
            required_owners=["frontend-dev"],
        )
        sec_block = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked",
            current_persona="daniel",
            required_owners=["security-eng", "devops-eng"],
        )
        _write(
            tmp_telemetry,
            [front_block, front_block, sec_block],
        )
        result = summarise("all", path=tmp_telemetry)
        owners = dict(result.top_owners_required)
        assert owners["frontend-dev"] == 2
        assert owners["security-eng"] == 1
        assert owners["devops-eng"] == 1

    def test_blocked_with_no_persona_uses_unknown(
        self, tmp_telemetry: Path
    ):
        now = datetime.now(timezone.utc)
        entry = _entry(
            ts=now,
            allow=False,
            reason="lead-blocked",
            current_persona=None,
            required_owners=["frontend-dev"],
        )
        _write(tmp_telemetry, [entry])
        result = summarise("all", path=tmp_telemetry)
        personas = dict(result.top_blocked_personas)
        assert personas["unknown"] == 1
