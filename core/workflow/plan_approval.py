"""Per-session plan-approval state machine (Interaction Reform PR3).

The flow contract says Gate 2 "waits for EXPLICIT user approval", but
nothing executable ever verified it — the enforcer only checked marker
PRESENCE, so a bare ``[arka:routing]`` unlocked writes. This module
tracks the missing signal:

    none → presented → approved

- **presented** — the Stop hook observed the turn ending at Gate 2
  (plan shown, no Gate 3 yet).
- **approved** — the UserPromptSubmit hook classified the NEXT user
  message as an approval, or PostToolUse saw a successful
  ``ExitPlanMode`` (the native plan-mode approve button IS approval).

A new ``presented`` invalidates an older ``approved`` (plan B after an
approved plan A requires fresh approval): approval is only live when
``approved_ts >= presented_ts``.

Same persistence contract as ``flow_authorization``: CWE-22-safe state
files under ``arkaos_temp_dir`` (override ``ARKA_PLAN_APPROVAL_DIR``),
12h TTL, never raises — hooks must not break a turn. In PR3 the
enforcer only WARNS on missing approval (telemetry to measure false
positives across the install base); hard deny is PR4, gated on that
telemetry.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from core.shared.safe_session_id import safe_session_id
from core.shared.temp_paths import arkaos_temp_dir

DEFAULT_TTL_SECONDS = 12 * 60 * 60

_APPROVE_RE = re.compile(
    r"\b(aprovo|aprovado|avan[çc]a(?:m|mos)?|segue em frente|for[çc]a"
    r"|manda|bora|go ahead|approved?|proceed|ship it|lgtm)\b",
    re.IGNORECASE,
)
_REJECT_RE = re.compile(
    r"\b(n[ãa]o|para|espera|aguarda|cancela?|stop|reject|hold)\b",
    re.IGNORECASE,
)
_SHORT_YES_RE = re.compile(r"\b(sim|ok|okay|yes|yep|sure|dale)\b", re.IGNORECASE)


def _state_dir() -> Path | None:
    """Resolve the state dir, creating it. None when the mkdir fails.

    The module's never-raises contract must hold in its OWN internals:
    a read-only override dir or a full disk returns None (callers treat
    it as "no state") instead of propagating an OSError into a hook
    (QG 2026-07-09, PR4 prerequisite #3).
    """
    override = os.environ.get("ARKA_PLAN_APPROVAL_DIR", "").strip()
    try:
        if override:
            path = Path(override)
            path.mkdir(parents=True, exist_ok=True)
            return path
        return arkaos_temp_dir("arkaos-plan-approval")
    except OSError:
        return None


def _state_file(session_id: str) -> Path | None:
    safe = safe_session_id(session_id)
    if safe is None:
        return None
    state_dir = _state_dir()
    if state_dir is None:
        return None
    return state_dir / f"{safe}.json"


@dataclass
class ApprovalState:
    state: str = "none"  # none | presented | approved
    presented_ts: float = 0.0
    approved_ts: float = 0.0
    source: str = ""  # text | exit-plan-mode
    excerpt: str = ""


def _read(session_id: str) -> ApprovalState:
    path = _state_file(session_id)
    if path is None or not path.exists():
        return ApprovalState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ApprovalState(**{
            k: data.get(k, getattr(ApprovalState(), k))
            for k in ApprovalState().__dict__
        })
    except Exception:  # noqa: BLE001 — corrupt state resets, never raises
        return ApprovalState()


def _write(session_id: str, state: ApprovalState) -> None:
    path = _state_file(session_id)
    if path is None:
        return
    try:
        path.write_text(
            json.dumps(asdict(state)) + "\n", encoding="utf-8"
        )
    except OSError:
        return


def mark_presented(session_id: str) -> None:
    """The turn ended at Gate 2: a plan is on the table."""
    state = _read(session_id)
    state.state = "presented"
    state.presented_ts = time.time()
    _write(session_id, state)


def mark_approved(
    session_id: str, source: str = "text", excerpt: str = ""
) -> None:
    state = _read(session_id)
    state.state = "approved"
    state.approved_ts = time.time()
    state.source = source
    state.excerpt = excerpt[:120]
    _write(session_id, state)


def mark_rejected(session_id: str) -> None:
    _write(session_id, ApprovalState())


def get_state(session_id: str) -> ApprovalState:
    return _read(session_id)


def is_presented(session_id: str) -> bool:
    state = _read(session_id)
    return (
        state.state in ("presented", "approved")
        and time.time() - state.presented_ts < DEFAULT_TTL_SECONDS
    )


def is_approved(session_id: str) -> bool:
    """Approval is live only when it POSTdates the latest presented plan."""
    state = _read(session_id)
    if state.state != "approved" or not state.approved_ts:
        return False
    if state.approved_ts + 0.001 < state.presented_ts:
        return False
    return time.time() - state.approved_ts < DEFAULT_TTL_SECONDS


def classify_reply(text: str, has_creation_verb: bool = False) -> str:
    """Classify a user message that follows a presented plan.

    Returns "approve" | "reject" | "other". A short bare "sim/ok/yes"
    counts as approval ONLY when unambiguous: <= 5 tokens, no creation
    verb (a new instruction, not consent), and no question mark.
    """
    stripped = (text or "").strip()
    if not stripped:
        return "other"
    if _REJECT_RE.search(stripped):
        return "reject"
    if _APPROVE_RE.search(stripped) and not has_creation_verb:
        return "approve"
    tokens = stripped.split()
    if (
        len(tokens) <= 5
        and _SHORT_YES_RE.search(stripped)
        and not has_creation_verb
        and "?" not in stripped
    ):
        return "approve"
    return "other"
