"""Warn-only governance sweep for the Windows Stop hook.

``config/hooks/stop.sh`` hands the whole Stop event to
``core.hooks.stop``. ``stop.ps1`` cannot yet: it reimplements the event,
and this sweep used to live inside it as a ~100-line Python here-string --
source that no linter, no type checker and no test could reach, and that
a PowerShell drift guard could only ever inspect as text.

Promoting it to a module buys two things that a here-string cannot:

* ``_write_tmp_state`` is IMPORTED from ``core.hooks.stop`` instead of
  hand-copied. The copy had silently dropped the ``umask(0o077)``
  hardening and wrote ``0644``/``0755`` where the original writes
  ``0600``/``0700`` -- on transcript-derived payloads (sycophancy
  signals, phantom-action claims quoting assistant text) which, under the
  PowerShell adapter on POSIX, land in a shared ``/tmp``. Importing makes
  that class of loss impossible rather than merely tested-for.
* the parity test IMPORTS AND RUNS this module. The guard it replaced
  asserted module names were present as substrings of the .ps1, which a
  comment satisfies: the whole port could be neutered with every name
  left in place and all five tests still passed.

Scope is deliberately the NON-ENFORCEMENT subset. These detectors write
proposals and diagnostic state; nothing reads their output to gate
anything. The gating checks stay deferred with a recorded reason each --
see ``DEFERRED_IN_PS1`` in
``tests/python/test_stop_ps1_governance_parity.py``.

Every detector is fire-and-forget: a failure is skipped, never raised.
Observation must not be able to break the turn.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from pathlib import Path

# Imported, never mirrored -- see the module docstring.
from core.hooks.stop import _write_tmp_state

Detector = Callable[[str, str | None, str | None], None]


def _run_skill_proposer(last: str, raw: str | None, safe_sid: str | None) -> None:
    """Capability sweep — constitution rule ``mandatory-skill-evaluation``.

    The regression this whole port exists for: it ran on POSIX every turn
    and had never run on Windows once.
    """
    from core.governance.skill_proposer import evaluate

    evaluate(last)


def _run_sycophancy(last: str, raw: str | None, safe_sid: str | None) -> None:
    from core.governance.sycophancy_detector import detect_sycophancy

    verdict = detect_sycophancy(last)
    if verdict.is_sycophantic and safe_sid:
        _write_tmp_state("arkaos-sycophancy", safe_sid, {
            "is_sycophantic": verdict.is_sycophantic,
            "signals": verdict.signals,
            "confidence": verdict.confidence,
        })


def _run_phantom_actions(last: str, raw: str | None, safe_sid: str | None) -> None:
    from core.governance.phantom_action_check import check_phantom_actions

    result = check_phantom_actions(last, raw)
    if safe_sid:
        _write_tmp_state("arkaos-phantom", safe_sid, {
            "passed": result.passed,
            "reason": result.reason,
            "claims": result.claims,
            "suggestion": result.suggestion,
        })


def _run_tool_loops(last: str, raw: str | None, safe_sid: str | None) -> None:
    from core.governance.tool_loop_check import check_tool_loops

    verdict = check_tool_loops(raw)
    if verdict.detected and safe_sid:
        _write_tmp_state("arkaos-tool-loop", safe_sid, {
            "tool": verdict.tool,
            "repeats": verdict.repeats,
            "pattern": verdict.pattern,
            "total_tool_uses": verdict.total_tool_uses,
        })


# The ledger the parity test drives. A name here is a claim that the
# module RUNS; the test proves it by substituting each detector and
# asserting it was reached, so an entry cannot be satisfied by its own
# presence.
DETECTORS: tuple[tuple[str, Detector], ...] = (
    ("core.governance.skill_proposer", _run_skill_proposer),
    ("core.governance.sycophancy_detector", _run_sycophancy),
    ("core.governance.phantom_action_check", _run_phantom_actions),
    ("core.governance.tool_loop_check", _run_tool_loops),
)


def run(last: str, raw: str | None, safe_sid: str | None) -> list[str]:
    """Run every detector; return the names that completed.

    The return value exists for the parity test -- a caller in the hook
    discards it. One detector raising must not stop the others, which is
    why this is a loop over a table and not four nested try blocks.
    """
    completed: list[str] = []
    for name, detector in DETECTORS:
        try:
            detector(last, raw, safe_sid)
        except Exception:
            continue
        completed.append(name)
    return completed


def _last_assistant_message(transcript_path: str) -> str:
    with contextlib.suppress(Exception):
        from core.workflow.flow_enforcer import _load_last_assistant_messages

        messages = _load_last_assistant_messages(transcript_path, n=1)
        return messages[-1] if messages else ""
    return ""


def _raw_transcript(transcript_path: str) -> str | None:
    with contextlib.suppress(Exception):
        return Path(transcript_path).read_text(encoding="utf-8", errors="replace")
    return None


def _safe_sid(session_id: str) -> str | None:
    with contextlib.suppress(Exception):
        from core.shared.safe_session_id import safe_session_id

        return safe_session_id(session_id)
    return None


def main() -> int:
    """Entry point for ``python -m core.hooks.stop_governance``.

    Reads the same environment contract the sibling blocks in stop.ps1
    use (``TRANSCRIPT_PATH_VAL`` / ``SESSION_ID_VAL``). Always returns 0:
    the Stop hook is warn-only and must never fail the turn.
    """
    transcript_path = os.environ.get("TRANSCRIPT_PATH_VAL", "")
    if not transcript_path:
        return 0
    run(
        _last_assistant_message(transcript_path),
        _raw_transcript(transcript_path),
        _safe_sid(os.environ.get("SESSION_ID_VAL", "")),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
