"""Agent experience persistence — Quality Gate feedback loop store.

When Marta (CQO) rejects an agent's work, an `Experience` record is
appended to `~/.arkaos/agents/<agent_id>/experiences.jsonl`. The next
time that agent is dispatched, recent experiences are injected as
context so the agent inherits prior failures across sessions.

This closes the long-standing QG learning gap: rejection reports used
to live only in the PR thread; the agent that failed had no way to
recall the structural mistake on the next pass. The Paulo of next
month now sees what the Paulo of today learned the hard way.

PR3 of the Squad Intelligence Upgrade.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


AGENTS_ROOT: Path = Path.home() / ".arkaos" / "agents"


@dataclass
class Experience:
    """One QG verdict (or other lesson) captured for an agent.

    `patterns` is a list (not a single string) because a verdict can fail
    on multiple structural issues at once — e.g. function-length AND
    governance-gap. PR3 v3.74.0 changed from `pattern: str | None` to
    `patterns: list[str]` after Marta's QG-B6 ruled first-match-wins was
    masking secondary patterns.
    """

    ts: str
    agent_id: str
    session_id: str
    context: str
    verdict: str
    blockers: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    fix_applied: str | None = None
    references: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def experience_to_dict(exp: Experience) -> dict:
    """Public serialiser for callers that need to persist outside this store."""
    return asdict(exp)


@contextmanager
def _locked_append(path: Path):
    """Append to `path` under POSIX flock; Windows falls back to O_APPEND atomicity."""
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


def _safe_agent_id(agent_id: str) -> str | None:
    """Apply the same allowlist as session IDs (CWE-22 path-traversal guard)."""
    return _safe_session_id_module.safe_session_id(agent_id)


def _path_for(agent_id: str) -> Path | None:
    safe = _safe_agent_id(agent_id)
    if safe is None:
        return None
    return AGENTS_ROOT / safe / "experiences.jsonl"


def record_experience(experience: Experience) -> None:
    """Append an experience to the agent's JSONL.

    Silently drops the record when the agent_id fails the safe-id check
    or when filesystem I/O fails — recording must never block whatever
    triggered the QG verdict.
    """
    path = _path_for(experience.agent_id)
    if path is None:
        return
    try:
        with _locked_append(path) as fh:
            fh.write(json.dumps(asdict(experience)) + "\n")
    except OSError:
        return


def _parse_entry(line: str) -> Experience | None:
    """Decode one JSONL line into an Experience, or return None on bad input."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    try:
        return Experience(**data)
    except (TypeError, ValueError):
        return None


def _filter_entry(
    exp: Experience, since: datetime | None, tag: str | None
) -> bool:
    """Return True if the entry passes both filters."""
    if since is not None:
        try:
            ts = datetime.fromisoformat(exp.ts)
        except (TypeError, ValueError):
            return False
        if ts < since:
            return False
    if tag is not None and tag not in (exp.tags or []):
        return False
    return True


def _read_entries(
    path: Path, since: datetime | None, tag: str | None
) -> list[Experience]:
    """Parse the JSONL and apply filters. Empty on I/O error."""
    entries: list[Experience] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                exp = _parse_entry(line)
                if exp is None:
                    continue
                if _filter_entry(exp, since, tag):
                    entries.append(exp)
    except OSError:
        return []
    return entries


def query_experiences(
    agent_id: str,
    *,
    limit: int = 5,
    since: datetime | None = None,
    tag: str | None = None,
) -> list[Experience]:
    """Read experiences for an agent. Most recent first.

    Empty list when the agent has no record or the agent_id is unsafe.
    Malformed JSONL lines are skipped silently.
    """
    path = _path_for(agent_id)
    if path is None or not path.exists():
        return []
    entries = _read_entries(path, since, tag)
    entries.sort(key=lambda e: e.ts, reverse=True)
    return entries[:limit]
