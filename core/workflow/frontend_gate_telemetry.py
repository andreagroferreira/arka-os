"""Frontend-gate telemetry summarizer (Excellence Reform PR-D2).

Reads ``~/.arkaos/telemetry/frontend-gate.jsonl`` (the JSONL stream the
PreToolUse frontend gate appends on every gated decision) and produces
the evidence artifact for the WARN→hard flip decision: counts by
reason / marker_kind / mode / ui_scope, plus the would-have-denied rate
(suffix-scope events that hard mode would deny today).

Mirrors ``core.governance.specialist_telemetry`` so periods,
malformed-line tolerance, and zero-division safety behave the same way
across telemetry surfaces. Read-only.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH: Path = (
    Path.home() / ".arkaos" / "telemetry" / "frontend-gate.jsonl"
)
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})

# Reasons hard mode denies on suffix scope — the flip's FP surface.
_WOULD_DENY_REASONS = frozenset({"no-design-marker", "legacy-marker"})


@dataclass(frozen=True)
class FrontendGateSummary:
    """Aggregated frontend-gate telemetry over a time slice."""

    period: str
    total_events: int
    by_reason: list[tuple[str, int]] = field(default_factory=list)
    by_marker_kind: list[tuple[str, int]] = field(default_factory=list)
    by_mode: list[tuple[str, int]] = field(default_factory=list)
    by_ui_scope: list[tuple[str, int]] = field(default_factory=list)
    would_deny_events: int = 0
    would_deny_rate: float = 0.0
    corrupt_line_count: int = 0


def summarise(period: str, *, path: Path | None = None) -> FrontendGateSummary:
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
) -> FrontendGateSummary:
    # Only gated UI events matter for the flip; not-ui-scope is noise.
    gated = [e for e in entries if e.get("reason") != "not-ui-scope"]
    total = len(gated)
    reason_counter: Counter[str] = Counter()
    kind_counter: Counter[str] = Counter()
    mode_counter: Counter[str] = Counter()
    scope_counter: Counter[str] = Counter()
    would_deny = 0
    for e in gated:
        reason = str(e.get("reason", "unknown"))
        reason_counter[reason] += 1
        kind_counter[str(e.get("marker_kind", "unknown"))] += 1
        mode_counter[str(e.get("mode", "unknown"))] += 1
        scope = str(e.get("ui_scope", "suffix"))
        scope_counter[scope] += 1
        if reason in _WOULD_DENY_REASONS and scope == "suffix":
            would_deny += 1
    return FrontendGateSummary(
        period=period,
        total_events=total,
        by_reason=reason_counter.most_common(),
        by_marker_kind=kind_counter.most_common(),
        by_mode=mode_counter.most_common(),
        by_ui_scope=scope_counter.most_common(),
        would_deny_events=would_deny,
        would_deny_rate=(would_deny / total) if total else 0.0,
        corrupt_line_count=corrupt,
    )
