"""JSONL cost telemetry writer and aggregator for LLM completions.

One call == one line appended to `~/.arkaos/telemetry/llm-cost.jsonl`.
Writers are concurrent-safe on POSIX (fcntl advisory lock); on Windows
we rely on O_APPEND atomicity for line-sized writes. Never raises —
telemetry failures are swallowed so they cannot break a user-facing
completion call.

Per ADR-011 ("Token budgets are informational, not restrictive") this
module exposes aggregation helpers (`summarise`, `list_expensive_sessions`)
used by the `/arka costs` visibility command. NO hard caps are enforced
here — advisories are soft strings attached to the returned summary.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


DEFAULT_TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "llm-cost.jsonl"

VALID_PERIODS = ("today", "week", "month", "all")


def _telemetry_path() -> Path:
    override = os.environ.get("ARKA_LLM_COST_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_TELEMETRY_PATH


@contextmanager
def _locked_append(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a", encoding="utf-8")
    try:
        if _HAS_FLOCK:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield fh
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def record_cost(
    session_id: str,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cached_tokens: int,
    estimated_cost_usd: float | None,
) -> None:
    """Append one JSONL line describing an LLM call's cost.

    Silently swallows all errors. Telemetry must never break a
    completion call. The caller decides whether to compute the cost via
    `core.runtime.pricing.estimate_cost_usd` or pass None.
    """
    try:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": str(session_id or ""),
            "provider": str(provider or ""),
            "model": str(model or ""),
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
            "cached_tokens": int(cached_tokens or 0),
            "estimated_cost_usd": (
                float(estimated_cost_usd)
                if estimated_cost_usd is not None
                else None
            ),
        }
        with _locked_append(_telemetry_path()) as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetry must never raise
        return


def read_entries(path: Path | None = None) -> list[dict[str, Any]]:
    """Read and parse all JSONL entries from the telemetry file.

    Returns an empty list if the file does not exist. Malformed lines
    are skipped silently.
    """
    target = path or _telemetry_path()
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Aggregation layer (visibility-only, per ADR-011)
# ---------------------------------------------------------------------------


@dataclass
class CostSummary:
    """Aggregated cost view over a telemetry slice."""

    period: str
    total_cost_usd: float | None
    total_tokens_in: int
    total_tokens_out: int
    total_cached_tokens: int
    cache_hit_rate: float
    call_count: int
    by_provider: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_session: list[dict[str, Any]] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    corrupt_line_count: int = 0


def _period_cutoff(period: str, now: datetime | None = None) -> datetime | None:
    ref = now or datetime.now(timezone.utc)
    if period == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return ref - timedelta(days=7)
    if period == "month":
        return ref - timedelta(days=30)
    if period == "all":
        return None
    raise ValueError(f"invalid period: {period!r}")


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


def _zero_bucket() -> dict[str, Any]:
    return {
        "total_cost_usd": 0.0,
        "any_cost_known": False,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_cached_tokens": 0,
        "call_count": 0,
    }


def _accumulate(bucket: dict[str, Any], entry: dict[str, Any]) -> None:
    bucket["total_tokens_in"] += int(entry.get("tokens_in") or 0)
    bucket["total_tokens_out"] += int(entry.get("tokens_out") or 0)
    bucket["total_cached_tokens"] += int(entry.get("cached_tokens") or 0)
    bucket["call_count"] += 1
    cost = entry.get("estimated_cost_usd")
    if cost is not None:
        bucket["total_cost_usd"] += float(cost)
        bucket["any_cost_known"] = True


def _finalise_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    out = dict(bucket)
    if not out.pop("any_cost_known"):
        out["total_cost_usd"] = None
    else:
        out["total_cost_usd"] = round(out["total_cost_usd"], 6)
    tin = out["total_tokens_in"]
    out["cache_hit_rate"] = (
        round(out["total_cached_tokens"] / tin, 4) if tin > 0 else 0.0
    )
    return out


def _load_slice(
    path: Path | None,
    cutoff: datetime | None,
) -> tuple[list[dict[str, Any]], int]:
    target = path or _telemetry_path()
    if not target.exists():
        return [], 0
    kept: list[dict[str, Any]] = []
    corrupt = 0
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        if cutoff is not None:
            ts = _parse_ts(entry.get("ts"))
            if ts is None or ts < cutoff:
                continue
        kept.append(entry)
    return kept, corrupt


def _group(entries: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in entries:
        k = str(entry.get(key) or "")
        bucket = out.setdefault(k, _zero_bucket())
        _accumulate(bucket, entry)
    return {k: _finalise_bucket(v) for k, v in out.items()}


def _top_sessions(
    entries: list[dict[str, Any]], top_n: int
) -> list[dict[str, Any]]:
    grouped = _group(entries, "session_id")
    rows = [{"session_id": sid, **vals} for sid, vals in grouped.items()]
    rows.sort(key=lambda r: (r["total_cost_usd"] or 0.0), reverse=True)
    return rows[:top_n]


def _build_advisories(
    sessions: list[dict[str, Any]], threshold_usd: float
) -> list[str]:
    out: list[str] = []
    for row in sessions:
        cost = row.get("total_cost_usd") or 0.0
        if cost >= threshold_usd:
            out.append(
                f"Session {row['session_id'] or '<unknown>'} exceeded "
                f"${threshold_usd:.2f} (spent ${cost:.2f})"
            )
    return out


def _totals_bucket(entries: list[dict[str, Any]]) -> dict[str, Any]:
    totals = _zero_bucket()
    for entry in entries:
        _accumulate(totals, entry)
    return _finalise_bucket(totals)


def summarise(
    period: str = "today",
    path: Path | None = None,
    advisory_threshold_usd: float = 5.0,
    now: datetime | None = None,
) -> CostSummary:
    """Aggregate telemetry for the given period.

    Graceful on missing file, empty file, corrupt JSONL lines.
    Raises only on invalid `period` (programmer error).
    """
    if period not in VALID_PERIODS:
        raise ValueError(
            f"invalid period: {period!r}; expected one of {VALID_PERIODS}"
        )
    entries, corrupt = _load_slice(path, _period_cutoff(period, now=now))
    finalised = _totals_bucket(entries)
    sessions = _top_sessions(entries, top_n=10)
    return CostSummary(
        period=period,
        total_cost_usd=finalised["total_cost_usd"],
        total_tokens_in=finalised["total_tokens_in"],
        total_tokens_out=finalised["total_tokens_out"],
        total_cached_tokens=finalised["total_cached_tokens"],
        cache_hit_rate=finalised["cache_hit_rate"],
        call_count=finalised["call_count"],
        by_provider=_group(entries, "provider"),
        by_model=_group(entries, "model"),
        by_session=sessions,
        advisories=_build_advisories(sessions, advisory_threshold_usd),
        corrupt_line_count=corrupt,
    )


def list_expensive_sessions(
    path: Path | None = None,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Return the top-N sessions by total cost across the entire history."""
    entries, _ = _load_slice(path, cutoff=None)
    return _top_sessions(entries, top_n=max(0, int(top_n)))
