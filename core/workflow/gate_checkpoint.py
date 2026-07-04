"""Gate checkpoint persistence for the 4-gate evidence flow (v4.1.0).

Invoked by the Stop hook once per assistant turn. Scans recent assistant
messages for `[arka:gate:N]` markers and persists the furthest gate
observed to BOTH stores:

- ``~/.arkaos/workflow-state.json`` via :mod:`core.workflow.state`
- ``~/.arkaos/sessions/<id>/workflow-state.json`` via
  :class:`core.memory.session_store.SessionStore` (consumed by
  :mod:`core.memory.rehydrator` at SessionStart)

This is what makes a rate-limit or context-exhaustion interruption
resumable at the correct gate instead of restarting the flow. See ADR
``docs/adr/2026-07-04-evidence-flow.md``.

Never raises: checkpointing must not break a Stop hook.
"""

import json
import re
import sys

from core.memory.session_store import SessionStore, WorkflowSnapshot
from core.shared.safe_session_id import safe_session_id
from core.workflow import state
from core.workflow.flow_enforcer import _load_last_assistant_messages

GATES: tuple[str, ...] = (
    "gate-1-context",
    "gate-2-plan",
    "gate-3-execute",
    "gate-4-review",
)

GATE_MARKER_RE = re.compile(r"\[arka:gate:([1-4])\]", re.IGNORECASE)
GATE3_EVIDENCE_RE = re.compile(
    r"\[arka:gate:3\]\s*evidence:\s*(?P<evidence>.+)", re.IGNORECASE
)

_SCAN_WINDOW = 20


def extract_latest_gate(messages: list[str]) -> int | None:
    """Return the highest gate number observed across the messages."""
    latest: int | None = None
    for text in messages:
        for match in GATE_MARKER_RE.finditer(text):
            number = int(match.group(1))
            if latest is None or number > latest:
                latest = number
    return latest


def extract_gate3_evidence(messages: list[str]) -> str | None:
    """Return the most recent Gate-3 evidence line, if any."""
    evidence: str | None = None
    for text in messages:
        for match in GATE3_EVIDENCE_RE.finditer(text):
            evidence = match.group("evidence").strip()
    return evidence


def _phase_statuses(latest: int) -> dict[str, str]:
    """Map each gate to completed/in_progress/pending given the latest gate."""
    statuses: dict[str, str] = {}
    for index, gate in enumerate(GATES, start=1):
        if index < latest:
            statuses[gate] = "completed"
        elif index == latest:
            statuses[gate] = "in_progress"
        else:
            statuses[gate] = "pending"
    return statuses


def _persist_global_state(latest: int, project: str, evidence: str | None) -> None:
    current = state.get_state()
    if current is None or current.get("workflow") != "evidence-flow":
        state.init_workflow("evidence-flow", project, list(GATES))
    for gate, status in _phase_statuses(latest).items():
        artifact = None
        if gate == GATES[2] and evidence:
            artifact = evidence
        state.update_phase(gate, status, artifact=artifact)


def _persist_session_snapshot(
    session_id: str, latest: int, evidence: str | None
) -> None:
    safe = safe_session_id(session_id)
    if safe is None:
        return
    store = SessionStore(safe)
    snapshot = WorkflowSnapshot(
        workflow_id=safe,
        workflow_name="evidence-flow",
        current_phase=GATES[latest - 1],
        phases=_phase_statuses(latest),
        artifacts=[evidence] if evidence else [],
    )
    store.save_workflow_snapshot(snapshot)


def checkpoint(
    transcript_path: str, session_id: str, project: str = ""
) -> dict | None:
    """Persist the furthest observed gate. Returns a summary dict or None."""
    try:
        messages = _load_last_assistant_messages(transcript_path, _SCAN_WINDOW)
        latest = extract_latest_gate(messages)
        if latest is None:
            return None
        evidence = extract_gate3_evidence(messages)
        _persist_global_state(latest, project, evidence)
        _persist_session_snapshot(session_id, latest, evidence)
        return {
            "gate": latest,
            "current_phase": GATES[latest - 1],
            "evidence": evidence,
        }
    except Exception:  # noqa: BLE001 — a Stop hook must never break the turn
        return None


def main(argv: list[str]) -> int:
    """CLI: gate_checkpoint <transcript_path> <session_id> [project]."""
    if len(argv) < 2:
        return 0
    project = argv[2] if len(argv) > 2 else ""
    result = checkpoint(argv[0], argv[1], project)
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
