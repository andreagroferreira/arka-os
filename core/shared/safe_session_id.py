"""Shared session-id allowlist — path-traversal / injection guard.

A session id is considered safe iff it matches ``[A-Za-z0-9._-]{1,128}``.
Any other character (``/``, ``\\``, whitespace, control char, unicode,
NUL, ``..``) rejects — callers MUST treat ``None`` as "do not use this
id for any filesystem or shell path".

Why this lives here: the exact same regex + helper was duplicated in 6
modules (flow_enforcer, marker_cache, research_gate, kb_cache,
auto_documentor, auto_doc_worker). A single source of truth prevents
drift — if the allowlist ever tightens, it tightens everywhere.

Historic aliases remain at each call site as module-level re-exports
so external importers that did ``from core.workflow.flow_enforcer
import SAFE_SESSION_ID_RE`` continue to work.
"""

from __future__ import annotations

import re


SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def safe_session_id(session_id: str) -> str | None:
    """Validate ``session_id`` against the strict allowlist.

    Returns the id unchanged when safe, or ``None`` when it contains
    path separators, ``..`` traversal fragments, whitespace, unicode,
    NUL bytes, or any character outside ``[A-Za-z0-9._-]``. Length is
    capped at 128 characters to prevent pathological filesystem paths.

    Callers MUST treat ``None`` as reject — never construct a path or
    shell argument from the raw input when this returns ``None``.
    """
    if not session_id or not isinstance(session_id, str):
        return None
    if not SAFE_SESSION_ID_RE.match(session_id):
        return None
    return session_id
