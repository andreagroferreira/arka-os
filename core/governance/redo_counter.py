"""Quality Gate redo-loop counter (excellence-mandate, v4.2.0).

The constitution caps REJECTED redo cycles at 2 — a third REJECTED
escalates to the operator with the full verdict instead of another
silent retry. This module is the mechanical counter behind that rule
(previously declarative only).

State: ``~/.arkaos/quality-gate/redo-counters.json`` keyed by session id.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REDO_CAP = 2

# Session ids come from the caller; the marker writes into a path segment,
# so anything outside this alphabet skips the marker (the JSON counter,
# where the id is only a key, still records it).
_SAFE_SESSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _state_path() -> Path:
    """Resolved at call time so tests can repoint HOME — the import-time
    constant it replaces froze the REAL home before monkeypatching."""
    return Path.home() / ".arkaos" / "quality-gate" / "redo-counters.json"


def escalation_marker(session_id: str) -> Path | None:
    """Path of the on-disk escalation flag for a session (Gate Economy).

    The flag is what makes the cap ACTIONABLE instead of a returned
    string: the orchestrator (and any future dispatch gate) can test for
    it before opening another QG round. None for unsafe session ids.
    """
    if not _SAFE_SESSION_RE.fullmatch(session_id or ""):
        return None
    return (
        Path.home() / ".arkaos" / "quality-gate" / session_id / "ESCALATE"
    )


@dataclass(frozen=True)
class RedoState:
    session_id: str
    count: int
    escalate: bool

    def to_message(self) -> str:
        if not self.escalate:
            return (
                f"[arka:qg] REJECTED — redo cycle {self.count}/{REDO_CAP}. "
                f"Looping back to execution with the issue list."
            )
        return (
            f"[arka:qg:escalate] REJECTED {self.count} times — cap of "
            f"{REDO_CAP} redo cycles exceeded (excellence-mandate). "
            f"STOP: present the full verdict to the operator and wait for "
            f"a decision. Do not retry silently."
        )


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_rejected(session_id: str, path: Path | None = None) -> RedoState:
    """Increment the REJECTED counter; escalate above the cap.

    Crossing the cap also drops the on-disk ESCALATE marker for the
    session — the actionable half of the escalation (Gate Economy):
    a marker the next dispatch decision can test, not just a string
    the caller may ignore.
    """
    state_path = path or _state_path()
    data = _load(state_path)
    count = int(data.get(session_id, 0) or 0) + 1
    data[session_id] = count
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # counter must never block the gate itself
    state = RedoState(session_id=session_id, count=count,
                      escalate=count > REDO_CAP)
    if state.escalate:
        _write_marker(session_id, state)
    return state


def _write_marker(session_id: str, state: RedoState) -> None:
    marker = escalation_marker(session_id)
    if marker is None:
        return
    with contextlib.suppress(OSError):
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({
                "session_id": session_id,
                "count": state.count,
                "cap": REDO_CAP,
                "ts": datetime.now(UTC).isoformat(),
                "message": state.to_message(),
            }, indent=2),
            encoding="utf-8",
        )


def reset(session_id: str, path: Path | None = None) -> None:
    """Clear the counter and the escalation marker — called on APPROVED."""
    state_path = path or _state_path()
    data = _load(state_path)
    if session_id in data:
        del data[session_id]
        with contextlib.suppress(OSError):
            state_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
    marker = escalation_marker(session_id)
    if marker is not None:
        with contextlib.suppress(OSError):
            marker.unlink(missing_ok=True)


def current(session_id: str, path: Path | None = None) -> RedoState:
    """Read-only view of the counter."""
    count = int(_load(path or _state_path()).get(session_id, 0) or 0)
    return RedoState(session_id=session_id, count=count,
                     escalate=count > REDO_CAP)
