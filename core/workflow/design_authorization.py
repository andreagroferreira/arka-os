"""Persistent per-session design authorization — frontend-gate resilience.

The frontend gate reasons over a 20-message transcript window. Two
structural blind spots produce false denies in hard mode (the same class
the flow enforcer solved with ``flow_authorization``, "652 false
blocks"):

- the current turn's ``[arka:design]`` marker is invisible to that
  turn's own PreToolUse hook (a denied tool call never persists its
  turn's text to the transcript), and
- a tool-heavy sequence serializes as ``<tool_use:...>`` placeholders
  and rolls the marker's text block out of the window.

Fix: **persist-on-observe + consult-before-deny**. Whenever ``evaluate``
observes a structured marker in the window it confirms it here; when the
window shows nothing, a valid persisted confirmation for the session
still allows. Deliberately NO turn-grace tier: a session with no design
evidence at all must keep denying in hard mode (excellence-mandate), and
the first confirmation has a natural path — emit the marker in a turn
whose tools are not gated (loading skills / reading the design system),
which persists to the transcript and confirms on the next evaluation.

State dir: ``/tmp/arkaos-design-auth`` (override via
``ARKA_DESIGN_AUTH_DIR``).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module
from core.shared.temp_paths import arkaos_temp_dir

_safe_session_id = _safe_session_id_module.safe_session_id

# A working session; a stale /tmp record expires on its own.
DEFAULT_TTL_SECONDS = 12 * 60 * 60


def _base_dir() -> Path:
    override = os.environ.get("ARKA_DESIGN_AUTH_DIR", "").strip()
    return Path(override) if override else arkaos_temp_dir("arkaos-design-auth")


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


def confirm(session_id: str, marker: str) -> None:
    """Persist a confirmed design authorization (structured marker seen)."""
    path = _auth_path(session_id)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"marker": marker, "confirmed_ts": time.time()}),
            encoding="utf-8",
        )
    except OSError:
        pass  # authorization state must never block the hook


def confirmed_marker(
    session_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> str | None:
    """Return the persisted marker if present and within TTL, else None."""
    data = _read(_auth_path(session_id))
    ts = data.get("confirmed_ts")
    if ts is None:
        return None
    if time.time() - float(ts) > ttl_seconds:
        return None
    marker = data.get("marker")
    return marker if isinstance(marker, str) and marker else None


def is_confirmed(
    session_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> bool:
    return confirmed_marker(session_id, ttl_seconds) is not None


def clear(session_id: str) -> None:
    """Remove authorization state for a session (tests / session end)."""
    path = _auth_path(session_id)
    if path is None:
        return
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        pass
