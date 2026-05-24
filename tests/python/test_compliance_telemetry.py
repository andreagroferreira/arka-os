"""Tests for core.governance.compliance_telemetry (PR29 v2.48.0).

Summarizer over the stop-hook entries in
~/.arkaos/telemetry/enforcement.jsonl. Surfaces compliance with the
four contracts the session-start hook establishes:

  - closing_marker_found  ([arka:phase:13] / [arka:trivial])
  - meta_tag_found        ([arka:meta] one-liner — PR12 v2.34.0)
  - kb_cite_passed        (KB citation soft block — PR18 v2.40.0)
  - sycophancy clean      (sycophancy detector — PR13 v2.35.0)

Empty/missing file is a no-op (no false positives). Malformed lines
skipped. Periods today/week/month/all share the cutoff vocabulary
of enforcement_telemetry.summarise.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.governance.compliance_telemetry import (
    ComplianceSummary,
    summarise,
)


def _entry(
    ts: datetime,
    *,
    event: str = "stop-hook-flow-check",
    closing_marker_found: bool = True,
    meta_tag_found: bool = True,
    kb_cite_passed: bool = True,
    sycophancy_is_flagged: bool = False,
) -> dict:
    return {
        "ts": ts.isoformat(),
        "event": event,
        "closing_marker_found": closing_marker_found,
        "meta_tag_found": meta_tag_found,
        "kb_cite_passed": kb_cite_passed,
        "sycophancy_is_flagged": sycophancy_is_flagged,
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


# ─── Robustness ─────────────────────────────────────────────────────────


class TestRobustness:
    def test_missing_file_returns_zero(self, tmp_path: Path):
        result = summarise("all", path=tmp_path / "absent.jsonl")
        assert isinstance(result, ComplianceSummary)
        assert result.stop_events == 0

    def test_empty_file_returns_zero(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        assert result.stop_events == 0

    def test_non_stop_events_ignored(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            {"ts": now.isoformat(), "event": "enforcement", "allow": True},
            _entry(now),
        ])
        result = summarise("all", path=tmp_telemetry)
        # Only the stop-hook entry should count
        assert result.stop_events == 1

    def test_null_fields_excluded_from_rate(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            {
                "ts": now.isoformat(),
                "event": "stop-hook-flow-check",
                "meta_tag_found": None,
                "closing_marker_found": None,
                "kb_cite_passed": None,
                "sycophancy_is_flagged": None,
            },
            _entry(now),  # all True
        ])
        result = summarise("all", path=tmp_telemetry)
        # Null entries excluded from rate denominator
        assert result.meta_tag_rate == 1.0


# ─── Rates ──────────────────────────────────────────────────────────────


class TestRates:
    def test_perfect_compliance_returns_full_rates(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [_entry(now) for _ in range(5)])
        result = summarise("all", path=tmp_telemetry)
        assert result.closing_marker_rate == 1.0
        assert result.meta_tag_rate == 1.0
        assert result.kb_cite_pass_rate == 1.0
        assert result.sycophancy_clean_rate == 1.0

    def test_mixed_compliance(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(now, meta_tag_found=True),
            _entry(now, meta_tag_found=True),
            _entry(now, meta_tag_found=False),
            _entry(now, meta_tag_found=False),
        ])
        result = summarise("all", path=tmp_telemetry)
        assert result.meta_tag_rate == 0.5

    def test_sycophancy_clean_rate_inverts_flagged(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        _write(tmp_telemetry, [
            _entry(now, sycophancy_is_flagged=True),  # NOT clean
            _entry(now, sycophancy_is_flagged=False), # clean
            _entry(now, sycophancy_is_flagged=False), # clean
        ])
        result = summarise("all", path=tmp_telemetry)
        # 2 clean / 3 total
        assert abs(result.sycophancy_clean_rate - (2 / 3)) < 1e-9

    def test_zero_division_safety(self, tmp_telemetry: Path):
        _write(tmp_telemetry, [])
        result = summarise("all", path=tmp_telemetry)
        assert result.closing_marker_rate == 0.0
        assert result.meta_tag_rate == 0.0
        assert result.kb_cite_pass_rate == 0.0
        assert result.sycophancy_clean_rate == 0.0


# ─── Period filter ──────────────────────────────────────────────────────


class TestPeriod:
    def test_today_excludes_yesterday(self, tmp_telemetry: Path):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1, hours=2)
        _write(tmp_telemetry, [_entry(yesterday), _entry(now)])
        result = summarise("today", path=tmp_telemetry)
        assert result.stop_events == 1

    def test_invalid_period_raises(self, tmp_telemetry: Path):
        with pytest.raises(ValueError):
            summarise("yesterday-ish", path=tmp_telemetry)
