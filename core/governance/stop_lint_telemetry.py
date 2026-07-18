"""Stop-lint telemetry summarizer.

Reads the ``"event": "stop-lint"`` entries appended by
``core.governance.stop_lint`` to ``~/.arkaos/telemetry/stop-lint.jsonl``
and reports pass/would-block rates. This summary is the evidence that
gates any promotion of the stop-lint batch beyond WARN (the
frontend-gate ``would_deny_rate`` rollout pattern).

Mirrors the period vocabulary of ``compliance_telemetry.summarise``
(today / week / month / all). Empty/missing file = zero rates. Rates
are computed over *observed* runs only — skipped runs (no changed
files) are counted separately and excluded from denominators.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "stop-lint.jsonl"
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_EVENT: str = "stop-lint"


@dataclass(frozen=True)
class StopLintSummary:
    """Stop-lint snapshot over a slice of worker telemetry."""

    period: str
    runs: int
    skipped_runs: int
    lint_pass_rate: float
    typecheck_pass_rate: float
    would_block_rate: float
    corrupt_line_count: int = 0


def summarise(period: str, *, path: Path | None = None) -> StopLintSummary:
    """Return a StopLintSummary for the requested period."""
    if period not in _VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    src = path or DEFAULT_PATH
    cutoff = _period_cutoff(period)
    entries, corrupt = _read_entries(src, cutoff)
    return _build_summary(period, entries, corrupt)


def _period_cutoff(period: str, now: datetime | None = None) -> datetime | None:
    ref = now or datetime.now(UTC)
    if period == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return ref - timedelta(days=7)
    if period == "month":
        return ref - timedelta(days=30)
    return None


def _read_entries(
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
                if entry.get("event") != _EVENT:
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
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _build_summary(
    period: str,
    entries: Iterable[dict[str, Any]],
    corrupt: int,
) -> StopLintSummary:
    rows = list(entries)
    observed = [r for r in rows if r.get("overall") != "skipped"]
    return StopLintSummary(
        period=period,
        runs=len(rows),
        skipped_runs=len(rows) - len(observed),
        lint_pass_rate=_true_rate(observed, "lint_passed"),
        typecheck_pass_rate=_true_rate(observed, "typecheck_passed"),
        would_block_rate=_true_rate(observed, "would_block"),
        corrupt_line_count=corrupt,
    )


def _true_rate(rows: list[dict[str, Any]], key: str) -> float:
    observed = [r for r in rows if isinstance(r.get(key), bool)]
    if not observed:
        return 0.0
    return sum(1 for r in observed if r[key] is True) / len(observed)
