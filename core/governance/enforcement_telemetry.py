"""Enforcement telemetry summarizer (PR19 v2.41.0).

Reads ``~/.arkaos/telemetry/enforcement.jsonl`` (the JSONL stream the
PreToolUse hook appends to on every gated tool decision) and produces
compact summaries for ``/arka status`` and downstream tuning.

Mirrors the pattern of ``core.runtime.llm_cost_telemetry`` so periods,
malformed-line tolerance, and zero-division safety behave the same way
across the two telemetry surfaces. Read-only — never writes to the
JSONL itself.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_TOP_N: int = 5


@dataclass(frozen=True)
class EnforcementSummary:
    """Aggregated enforcement telemetry over a time slice."""
    period: str
    total_calls: int
    blocked_calls: int
    block_rate: float
    bypass_used: int
    top_blocked_tools: list[tuple[str, int]] = field(default_factory=list)
    top_block_reasons: list[tuple[str, int]] = field(default_factory=list)
    corrupt_line_count: int = 0


def summarise(period: str, *, path: Path | None = None) -> EnforcementSummary:
    """Return an EnforcementSummary for the requested period.

    period: one of "today", "week", "month", "all".
    path:   override telemetry source (used by tests; defaults to DEFAULT_PATH).
    """
    if period not in _VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    src = path or DEFAULT_PATH
    cutoff = _period_cutoff(period)
    entries, corrupt = _read_jsonl(src, cutoff)
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


def _read_jsonl(src: Path, cutoff: datetime | None) -> tuple[list[dict[str, Any]], int]:
    if not src.exists():
        return [], 0
    entries: list[dict[str, Any]] = []
    corrupt = 0
    # Line-stream the file to keep memory O(1) regardless of telemetry size.
    # A runaway hook could grow this file to multiple GB; reading it whole
    # would OOM the /arka status / /arka enforcement caller.
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
                if cutoff is not None and not _within_cutoff(entry, cutoff):
                    continue
                entries.append(entry)
    except OSError:
        return entries, corrupt
    return entries, corrupt


def _within_cutoff(entry: dict[str, Any], cutoff: datetime) -> bool:
    ts = _parse_ts(entry.get("ts"))
    if ts is None:
        return False
    return ts >= cutoff


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
) -> EnforcementSummary:
    total = 0
    blocked = 0
    bypass = 0
    blocked_tools: Counter[str] = Counter()
    block_reasons: Counter[str] = Counter()
    for entry in entries:
        total += 1
        if entry.get("bypass_used"):
            bypass += 1
        if entry.get("allow") is False:
            blocked += 1
            tool = str(entry.get("tool", ""))
            reason = str(entry.get("reason", ""))
            if tool:
                blocked_tools[tool] += 1
            if reason:
                block_reasons[reason] += 1
    return EnforcementSummary(
        period=period,
        total_calls=total,
        blocked_calls=blocked,
        block_rate=(blocked / total) if total else 0.0,
        bypass_used=bypass,
        top_blocked_tools=blocked_tools.most_common(_TOP_N),
        top_block_reasons=block_reasons.most_common(_TOP_N),
        corrupt_line_count=corrupt,
    )
