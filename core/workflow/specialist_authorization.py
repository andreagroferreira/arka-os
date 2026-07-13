"""Persistent per-session persona — closes the specialist gate fail-open.

The specialist gate reads the persona from the last ``[arka:routing]`` /
``[arka:dispatch]`` marker in a 20-message window. When the marker rolls
out of the window the gate returned ALLOW (``no-routing-tag``) — 4,093
of 5,683 telemetry records (72%). Routing once and hammering the gate
with 20 messages of noise was a winning strategy.

Fix mirrors ``design_authorization`` (#297, frontend gate): **persist on
observe, consult before allow**. Whenever ``evaluate`` sees a marker in
the window it confirms the resolved persona here; when the window shows
nothing, a valid persisted persona for the session decides exactly as if
the marker were still visible — including deciding BLOCK.

Two deliberate properties:

- **The record is keyed by session_id AND the transcript file's name.**
  A dispatched subagent runs on its own transcript (ADR
  2026-05-28-specialist-dispatch-subagent-blindspot), so it can never
  inherit the parent's persisted persona and be blocked from the very
  files it was dispatched to write — even if it shares the session_id.
- **A session that never routed stays un-restored** (``never-routed``
  keeps today's ALLOW): this module only closes the eviction hole; the
  hard flip for never-routed sessions is a separate, telemetry-gated
  decision.

State dir: ``/tmp/arkaos-specialist-auth`` (override via
``ARKA_SPECIALIST_AUTH_DIR``).
"""

from __future__ import annotations

import contextlib
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
    override = os.environ.get("ARKA_SPECIALIST_AUTH_DIR", "").strip()
    return Path(override) if override else arkaos_temp_dir(
        "arkaos-specialist-auth"
    )


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


def confirm(
    session_id: str,
    transcript_path: str,
    persona: str,
    marker: str,
    persona_raw: str | None = None,
    alias_resolved: bool = False,
) -> None:
    """Persist the persona observed in the window (marker seen)."""
    if not persona or not transcript_path:
        return
    path = _auth_path(session_id)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "persona": persona,
                "marker": marker,
                "persona_raw": persona_raw,
                "alias_resolved": bool(alias_resolved),
                "transcript": Path(transcript_path).name,
                "confirmed_ts": time.time(),
            }),
            encoding="utf-8",
        )
    except OSError:
        pass  # authorization state must never block the hook


def confirmed(
    session_id: str,
    transcript_path: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict | None:
    """Return the persisted persona record, or None.

    None unless: record exists, TTL holds, the persona is non-empty AND
    the record was written for THIS transcript file — the property that
    keeps a parent's persona out of a subagent's evaluation.
    """
    if not transcript_path:
        return None
    data = _read(_auth_path(session_id))
    ts = data.get("confirmed_ts")
    if ts is None or time.time() - float(ts) > ttl_seconds:
        return None
    if data.get("transcript") != Path(transcript_path).name:
        return None
    persona = data.get("persona")
    if not isinstance(persona, str) or not persona:
        return None
    return data


def clear(session_id: str) -> None:
    """Remove authorization state for a session (tests / session end)."""
    path = _auth_path(session_id)
    if path is None:
        return
    with contextlib.suppress(FileNotFoundError, OSError):
        path.unlink()
