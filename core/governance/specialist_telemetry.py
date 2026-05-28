"""Specialist-dispatch telemetry summarizer (PR1 — Squad Intelligence Upgrade).

Reads ``~/.arkaos/telemetry/specialist-dispatch.jsonl`` (the JSONL stream
the PreToolUse specialist-enforcer appends to on every gated decision)
and produces compact summaries for ``/arka status`` and tuning.

Mirrors the pattern of ``core.governance.enforcement_telemetry`` so
periods, malformed-line tolerance, and zero-division safety behave the
same way across telemetry surfaces. Read-only.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH: Path = (
    Path.home() / ".arkaos" / "telemetry" / "specialist-dispatch.jsonl"
)
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_TOP_N: int = 5


@dataclass(frozen=True)
class SpecialistSummary:
    """Aggregated specialist-dispatch telemetry over a time slice."""
    period: str
    total_calls: int
    blocked_calls: int
    block_rate: float
    bypass_used: int
    top_blocked_personas: list[tuple[str, int]] = field(default_factory=list)
    top_owners_required: list[tuple[str, int]] = field(default_factory=list)
    corrupt_line_count: int = 0


def summarise(period: str, *, path: Path | None = None) -> SpecialistSummary:
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


def _read_jsonl(
    src: Path, cutoff: datetime | None
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
                if cutoff is not None:
                    ts_raw = entry.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw)
                    except (TypeError, ValueError):
                        corrupt += 1
                        continue
                    if ts < cutoff:
                        continue
                entries.append(entry)
    except OSError:
        return entries, corrupt
    return entries, corrupt


def _build_summary(
    period: str, entries: list[dict[str, Any]], corrupt: int
) -> SpecialistSummary:
    total = len(entries)
    blocked = sum(1 for e in entries if e.get("allow") is False)
    bypass = sum(1 for e in entries if e.get("bypass_used") is True)
    rate = (blocked / total) if total else 0.0
    persona_counter: Counter[str] = Counter()
    owner_counter: Counter[str] = Counter()
    for e in entries:
        if e.get("allow") is False:
            persona = e.get("current_persona") or "unknown"
            persona_counter[persona] += 1
            for owner in e.get("required_owners", []) or []:
                owner_counter[owner] += 1
    return SpecialistSummary(
        period=period,
        total_calls=total,
        blocked_calls=blocked,
        block_rate=rate,
        bypass_used=bypass,
        top_blocked_personas=persona_counter.most_common(_TOP_N),
        top_owners_required=owner_counter.most_common(_TOP_N),
        corrupt_line_count=corrupt,
    )
