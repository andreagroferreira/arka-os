"""Persistent per-session flow authorization — enforcer resilience.

Claude Code exposes NO hook access to the current assistant message
(confirmed against the hook docs, 2026-07-05: neither PreToolUse nor
PostToolUse carries the message text, and the transcript at
``transcript_path`` does not yet include the in-progress turn). So the
current turn's ``[arka:routing]`` marker is structurally invisible to
that turn's own tool calls, and the old PostToolUse marker cache read a
non-existent ``assistant_message`` field — it was never written, leaving
the enforcer with only a 20-message transcript window that a long
session or a context compaction empties (652 false-positive blocks
observed in one session).

This module rebuilds resilience on what hooks CAN see: markers observed
in the transcript (past turns) plus persistent ``/tmp`` state that
survives compaction and window-rolling.

Two tiers:

- **CONFIRMED** — written whenever a flow marker is actually observed in
  the transcript. Valid for a session TTL, survives compaction. Grants
  a silent allow. This is the normal steady state: route once, then
  every subsequent turn is authorised.
- **TURN GRACE** — the current turn's marker cannot be seen, so the very
  first turn of a session (before any marker reaches the transcript) has
  no confirmed auth. Rather than a false-positive block, the turn is
  allowed WITH A WARNING and a per-turn grace flag so the rest of the
  turn proceeds. A never-routing session is warned every turn and, after
  ``GRACE_CAP`` consecutive graced turns with no confirmation, escalates
  to a hard block — a normally-routing session confirms by turn 2 and
  never reaches the cap.

State dir: ``/tmp/arkaos-flow-auth`` (override via ``ARKA_FLOW_AUTH_DIR``).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module

_safe_session_id = _safe_session_id_module.safe_session_id

# A working session; after this a stale /tmp record expires on its own.
DEFAULT_TTL_SECONDS = 12 * 60 * 60
# Consecutive graced turns with no confirmation before a hard block.
GRACE_CAP = 3

VALID_MARKER_TYPES: frozenset[str] = frozenset(
    {"routing", "trivial", "gate", "phase"}
)


@dataclass(frozen=True)
class GraceState:
    count: int
    escalate: bool


def _base_dir() -> Path:
    override = os.environ.get("ARKA_FLOW_AUTH_DIR", "").strip()
    return Path(override) if override else Path("/tmp/arkaos-flow-auth")


def _auth_path(session_id: str) -> Path | None:
    safe = _safe_session_id(session_id)
    return (_base_dir() / f"{safe}.json") if safe else None


def _read(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path | None, data: dict) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # authorization state must never block the hook


def confirm(session_id: str, marker_type: str) -> None:
    """Persist a confirmed authorization (a marker was observed)."""
    if marker_type not in VALID_MARKER_TYPES:
        return
    path = _auth_path(session_id)
    if path is None:
        return
    _write(path, {
        "marker_type": marker_type,
        "confirmed_ts": time.time(),
        "grace_count": 0,  # confirmation clears accumulated grace
        "turn_grace": False,
    })


def confirmed_record(
    session_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> dict | None:
    """Return the confirmed record if present and within TTL, else None."""
    data = _read(_auth_path(session_id))
    ts = data.get("confirmed_ts")
    if ts is None:
        return None
    if time.time() - float(ts) > ttl_seconds:
        return None
    return data


def is_confirmed(
    session_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> bool:
    return confirmed_record(session_id, ttl_seconds) is not None


def grant_turn_grace(session_id: str) -> None:
    """Flag the current turn as graced so its remaining tools pass."""
    path = _auth_path(session_id)
    if path is None:
        return
    data = _read(path)
    data["turn_grace"] = True
    _write(path, data)


def has_turn_grace(session_id: str) -> bool:
    return bool(_read(_auth_path(session_id)).get("turn_grace"))


def reset_turn(session_id: str) -> None:
    """Clear the per-turn grace flag (called at each new user prompt).

    Confirmed authorization and the grace counter are preserved — only
    the within-turn flag resets, so the next turn re-evaluates.
    """
    path = _auth_path(session_id)
    if path is None:
        return
    data = _read(path)
    if data.get("turn_grace"):
        data["turn_grace"] = False
        _write(path, data)


def grace_count(session_id: str) -> int:
    return int(_read(_auth_path(session_id)).get("grace_count", 0) or 0)


def register_grace(session_id: str) -> GraceState:
    """Increment the consecutive-grace counter; escalate past the cap."""
    path = _auth_path(session_id)
    if path is None:
        return GraceState(count=0, escalate=False)
    data = _read(path)
    count = int(data.get("grace_count", 0) or 0) + 1
    data["grace_count"] = count
    _write(path, data)
    return GraceState(count=count, escalate=count > GRACE_CAP)


def clear(session_id: str) -> None:
    """Remove all authorization state for a session (tests / session end)."""
    path = _auth_path(session_id)
    if path is None:
        return
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        pass
