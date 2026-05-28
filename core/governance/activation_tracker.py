"""Activation Tracker — PR5 Squad Intelligence Upgrade v3.76.0.

Counts how often each agent (`subagent_type`) is dispatched via the Agent
tool. Surfaces top callers and dead agents (no activation in N days).

Wired into the PostToolUse hook in a later task. For now: persistence +
query layer. Mirrors the JSONL + path-safe pattern of agent_experiences.py.
"""

from __future__ import annotations

import json
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


# ─── Module-level constant (monkeypatched by tests) ───────────────────────────

TELEMETRY_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "agent-activations.jsonl"


# ─── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class Activation:
    ts: str
    subagent_type: str
    session_id: str


# ─── Internal helpers ─────────────────────────────────────────────────────────

@contextmanager
def _locked_append(path: Path):
    """Append to path under POSIX flock; Windows falls back to O_APPEND atomicity."""
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


def _safe_id(value: str) -> str | None:
    """Delegate to safe_session_id for CWE-22 path-traversal guard."""
    return _safe_session_id_module.safe_session_id(value)


def _parse_ts(iso: str) -> datetime | None:
    """Parse an ISO timestamp string; return None on any failure."""
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _load_all() -> list[dict]:
    """Single-pass read of TELEMETRY_PATH; skip malformed lines silently."""
    entries: list[dict] = []
    try:
        with TELEMETRY_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return entries


def _filter_by_since(entries: list[dict], since: datetime | None) -> list[dict]:
    """Remove entries whose ts is strictly before `since`. Pass-through when since is None."""
    if since is None:
        return entries
    result: list[dict] = []
    for e in entries:
        ts = _parse_ts(e.get("ts", ""))
        if ts is not None and ts >= since:
            result.append(e)
    return result


def _most_recent_per_agent(entries: list[dict]) -> dict[str, str]:
    """Return a map of subagent_type → latest ts string seen across all entries."""
    latest: dict[str, str] = {}
    for e in entries:
        agent = e.get("subagent_type", "")
        ts = e.get("ts", "")
        if not agent or not ts:
            continue
        if agent not in latest or ts > latest[agent]:
            latest[agent] = ts
    return latest


# ─── Public API ───────────────────────────────────────────────────────────────

def record_activation(subagent_type: str, session_id: str) -> None:
    """Append one JSONL activation record to TELEMETRY_PATH.

    Silently drops when subagent_type is empty, fails the safe-id check,
    or when filesystem I/O fails.
    """
    if not subagent_type:
        return
    if _safe_id(subagent_type) is None:
        return
    record = asdict(Activation(
        ts=datetime.now(timezone.utc).isoformat(),
        subagent_type=subagent_type,
        session_id=session_id,
    ))
    try:
        with _locked_append(TELEMETRY_PATH) as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        return


def query_top_callers(
    *,
    limit: int = 10,
    since: datetime | None = None,
) -> list[tuple[str, int]]:
    """Return the most-dispatched subagent types in descending count order.

    Reads TELEMETRY_PATH, skips malformed lines silently. Optional `since`
    filters to activations at or after that datetime. Capped at `limit`.
    Empty store returns [].
    """
    entries = _load_all()
    entries = _filter_by_since(entries, since)
    counter: Counter[str] = Counter()
    for e in entries:
        agent = e.get("subagent_type", "")
        if agent:
            counter[agent] += 1
    return counter.most_common(limit)


def query_dead_agents(*, since_days: int = 30) -> list[tuple[str, str]]:
    """Return agents whose most-recent activation is older than `since_days`.

    Returns [(subagent_type, last_seen_ts), ...] sorted ascending by
    last_seen_ts (most-dormant first). Agents activated within the window
    are excluded even if they have older activations too.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    entries = _load_all()
    recent_map = _most_recent_per_agent(entries)
    dead: list[tuple[str, str]] = []
    for agent, last_ts in recent_map.items():
        ts = _parse_ts(last_ts)
        if ts is not None and ts < cutoff:
            dead.append((agent, last_ts))
    dead.sort(key=lambda pair: pair[1])
    return dead
