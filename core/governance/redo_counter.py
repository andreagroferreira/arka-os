"""Quality Gate redo-loop counter (excellence-mandate, v4.2.0).

The constitution caps REJECTED redo cycles at 2 — a third REJECTED
escalates to the operator with the full verdict instead of another
silent retry. This module is the mechanical counter behind that rule
(previously declarative only).

State: ``~/.arkaos/quality-gate/redo-counters.json`` keyed by session id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REDO_CAP = 2

_STATE_PATH = Path.home() / ".arkaos" / "quality-gate" / "redo-counters.json"


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
    """Increment the REJECTED counter; escalate above the cap."""
    state_path = path or _STATE_PATH
    data = _load(state_path)
    count = int(data.get(session_id, 0) or 0) + 1
    data[session_id] = count
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # counter must never block the gate itself
    return RedoState(session_id=session_id, count=count,
                     escalate=count > REDO_CAP)


def reset(session_id: str, path: Path | None = None) -> None:
    """Clear the counter — called on APPROVED."""
    state_path = path or _STATE_PATH
    data = _load(state_path)
    if session_id in data:
        del data[session_id]
        try:
            state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass


def current(session_id: str, path: Path | None = None) -> RedoState:
    """Read-only view of the counter."""
    count = int(_load(path or _STATE_PATH).get(session_id, 0) or 0)
    return RedoState(session_id=session_id, count=count,
                     escalate=count > REDO_CAP)
