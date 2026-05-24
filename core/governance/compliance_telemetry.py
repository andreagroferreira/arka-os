"""Behavior compliance telemetry summarizer (PR29 v2.48.0).

Reads the stop-hook entries in ``~/.arkaos/telemetry/enforcement.jsonl``
and reports compliance with the four contracts the session-start hook
establishes:

  - closing_marker_found  — [arka:phase:13] or [arka:trivial] present
  - meta_tag_found        — [arka:meta] one-liner present (PR12)
  - kb_cite_passed        — KB citation soft block result (PR18)
  - sycophancy clean      — inverse of sycophancy_is_flagged (PR13)

Mirrors the period vocabulary of ``enforcement_telemetry.summarise``
(today / week / month / all). Empty/missing file = no-op zero rates.
Null fields excluded from denominators so rates reflect *observed*
behavior, not ``unknown``-padded data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_STOP_EVENT: str = "stop-hook-flow-check"


@dataclass(frozen=True)
class ComplianceSummary:
    """Compliance snapshot over a slice of stop-hook telemetry."""
    period: str
    stop_events: int
    closing_marker_rate: float
    meta_tag_rate: float
    kb_cite_pass_rate: float
    sycophancy_clean_rate: float
    corrupt_line_count: int = 0


def summarise(period: str, *, path: Path | None = None) -> ComplianceSummary:
    """Return a ComplianceSummary for the requested period."""
    if period not in _VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    src = path or DEFAULT_PATH
    cutoff = _period_cutoff(period)
    entries, corrupt = _read_stop_entries(src, cutoff)
    return _build_summary(period, entries, corrupt)


def _period_cutoff(period: str, now: datetime | None = None) -> datetime | None:
    ref = now or datetime.now(timezone.utc)
    if period == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return ref - timedelta(days=7)
    if period == "month":
        return ref - timedelta(days=30)
    return None


def _read_stop_entries(
    src: Path, cutoff: datetime | None,
) -> tuple[list[dict[str, Any]], int]:
    if not src.exists():
        return [], 0
    entries: list[dict[str, Any]] = []
    corrupt = 0
    try:
        with src.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    corrupt += 1
                    continue
                if not isinstance(entry, dict):
                    corrupt += 1
                    continue
                if entry.get("event") != _STOP_EVENT:
                    continue
                if cutoff is not None and not _within_cutoff(entry, cutoff):
                    continue
                entries.append(entry)
    except OSError:
        return entries, corrupt
    return entries, corrupt


def _within_cutoff(entry: dict[str, Any], cutoff: datetime) -> bool:
    ts = _parse_ts(entry.get("ts"))
    return ts is not None and ts >= cutoff


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_summary(
    period: str,
    entries: Iterable[dict[str, Any]],
    corrupt: int,
) -> ComplianceSummary:
    rows = list(entries)
    return ComplianceSummary(
        period=period,
        stop_events=len(rows),
        closing_marker_rate=_true_rate(rows, "closing_marker_found"),
        meta_tag_rate=_true_rate(rows, "meta_tag_found"),
        kb_cite_pass_rate=_true_rate(rows, "kb_cite_passed"),
        sycophancy_clean_rate=_false_rate(rows, "sycophancy_is_flagged"),
        corrupt_line_count=corrupt,
    )


def _true_rate(rows: list[dict[str, Any]], key: str) -> float:
    observed = [r for r in rows if isinstance(r.get(key), bool)]
    if not observed:
        return 0.0
    return sum(1 for r in observed if r[key] is True) / len(observed)


def _false_rate(rows: list[dict[str, Any]], key: str) -> float:
    """Rate of `key is False` among rows where the field was observed."""
    observed = [r for r in rows if isinstance(r.get(key), bool)]
    if not observed:
        return 0.0
    return sum(1 for r in observed if r[key] is False) / len(observed)
