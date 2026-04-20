"""Turn-scoped flow marker cache.

Written by post-tool-use hook when [arka:routing] or [arka:trivial] is
emitted. Invalidated by user-prompt-submit hook at each new turn.
Used by flow_enforcer as an ACCELERATOR for allow decisions only.

ADR compliance (docs/adr/2026-04-17-binding-flow-enforcement.md):
- Cache is only ever consulted to ALLOW faster; transcript remains the
  authoritative source for any deny decision.
- Absence of a cache entry never, by itself, produces a deny — the
  caller must still fall back to the transcript scan.
"""

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module


def _resolve_cache_dir() -> Path:
    override = os.environ.get("ARKA_MARKER_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    return Path("/tmp/arkaos-flow-marker")


MARKER_CACHE_DIR = _resolve_cache_dir()
# Re-export for backward compatibility with any external importers.
SAFE_SESSION_ID_RE = _safe_session_id_module.SAFE_SESSION_ID_RE
VALID_MARKER_TYPES: frozenset[str] = frozenset({"routing", "trivial", "phase"})
_MAX_LABEL_LEN = 64


@dataclass
class MarkerRecord:
    """Internal representation of a cache record prior to JSON serialization."""

    marker_type: str
    dept: str
    lead: str
    turn_start_ts: float

    def to_dict(self) -> dict:
        return {
            "marker_type": self.marker_type,
            "dept": self.dept,
            "lead": self.lead,
            "turn_start_ts": self.turn_start_ts,
        }


_safe_session_id = _safe_session_id_module.safe_session_id


def _cache_path(session_id: str) -> Path | None:
    safe = _safe_session_id(session_id)
    if safe is None:
        return None
    # Re-resolve per call so monkeypatching MARKER_CACHE_DIR (tests) and
    # ARKA_MARKER_CACHE_DIR (hooks) both work.
    current_root = MARKER_CACHE_DIR
    env_override = os.environ.get("ARKA_MARKER_CACHE_DIR", "").strip()
    if env_override:
        current_root = Path(env_override)
    return current_root / f"{safe}.json"


def write_marker(
    session_id: str,
    marker_type: str,
    dept: str = "",
    lead: str = "",
) -> None:
    """Persist a marker for `session_id`. Atomic: tmp + rename."""
    if marker_type not in VALID_MARKER_TYPES:
        return
    path = _cache_path(session_id)
    if path is None:
        return
    record = MarkerRecord(
        marker_type=marker_type,
        dept=str(dept or "")[:_MAX_LABEL_LEN],
        lead=str(lead or "")[:_MAX_LABEL_LEN],
        turn_start_ts=time.time(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # Per-writer unique suffix prevents the "two writers pick the same tmp
    # name, one renames first, the other's tmp vanishes" race.
    unique = f"{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex}"
    tmp = path.with_suffix(path.suffix + f".{unique}.tmp")
    try:
        tmp.write_text(json.dumps(record.to_dict()), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def read_marker(session_id: str) -> dict | None:
    """Return the cached marker dict, or None if absent / unreadable."""
    path = _cache_path(session_id)
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("marker_type") not in VALID_MARKER_TYPES:
        return None
    return data


def invalidate_marker(session_id: str) -> None:
    """Remove the cached marker for `session_id`. Idempotent."""
    path = _cache_path(session_id)
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def is_valid_for_current_turn(session_id: str, user_prompt_ts: float) -> bool:
    """Return True iff a marker exists AND was written after `user_prompt_ts`.

    Callers that know the timestamp of the latest user prompt can use
    this to discard stale markers that survived a missed invalidation.
    """
    marker = read_marker(session_id)
    if marker is None:
        return False
    written_at = float(marker.get("turn_start_ts") or 0.0)
    return written_at >= user_prompt_ts
