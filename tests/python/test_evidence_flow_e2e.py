"""E2E test of the 4-gate evidence flow (v4.1.0 open item).

Simulates the full "one prompt -> delivery" lifecycle with an INDUCED
Gate-3 failure: G1 -> G2 -> G3 (tests fail, exit 1 on record) -> G3
retry (exit 0) -> G4, checkpointing after every turn like the Stop hook
does, then resumes the session through the rehydrator and asserts the
evidence floor cannot be bypassed at the Quality Gate.

All filesystem writes are redirected to tmp_path via HOME monkeypatching —
never touch the real ~/.arkaos (constitution: destructive primitives are
stubbed in cross-cutting tests).
"""

import json
from pathlib import Path

import pytest

from core.governance.review_workflow import ReviewWorkflowEngine, Verdict
from core.memory.rehydrator import rehydrate_session
from core.memory.session_store import SessionMeta, SessionStore
from core.workflow.gate_checkpoint import checkpoint

SESSION = "sess-e2e-flow"

TURNS: list[str] = [
    "[arka:routing] dev -> Paulo\n[arka:gate:1] context grounded",
    "[arka:gate:2] plan approved by operator",
    "[arka:gate:3] evidence: pytest tests/ -q -> exit 1 (2 failed)",
    "[arka:gate:3] evidence: pytest tests/ -q -> exit 0 (48 passed)",
    "[arka:gate:4] review: executable checks green, honest summary",
]


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


def _write_transcript(path: Path, assistant_texts: list[str]) -> Path:
    records = [{"role": "user", "content": "build the feature"}]
    records.extend(
        {"role": "assistant", "content": text} for text in assistant_texts
    )
    path.write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8"
    )
    return path


def _global_state(tmp_path: Path) -> dict:
    return json.loads(
        (tmp_path / ".arkaos" / "workflow-state.json").read_text()
    )


def _checkpoint_turns(tmp_path: Path, upto: int) -> dict | None:
    """Checkpoint with the transcript as it exists after turn `upto`."""
    transcript = _write_transcript(tmp_path / "t.jsonl", TURNS[:upto])
    return checkpoint(str(transcript), SESSION)


class TestFullLifecycleWithInducedFailure:
    def test_gate_progression_turn_by_turn(self, tmp_path):
        expected = [
            (1, "gate-1-context", None),
            (2, "gate-2-plan", None),
            (3, "gate-3-execute", "pytest tests/ -q -> exit 1 (2 failed)"),
            (3, "gate-3-execute", "pytest tests/ -q -> exit 0 (48 passed)"),
            (4, "gate-4-review", "pytest tests/ -q -> exit 0 (48 passed)"),
        ]
        for turn, (gate, phase, evidence) in enumerate(expected, start=1):
            result = _checkpoint_turns(tmp_path, turn)
            assert result == {
                "gate": gate,
                "current_phase": phase,
                "evidence": evidence,
            }, f"turn {turn} checkpoint mismatch"

    def test_induced_failure_lands_on_record_then_retry_overwrites(
        self, tmp_path
    ):
        _checkpoint_turns(tmp_path, 3)  # G3 with exit 1
        state = _global_state(tmp_path)
        assert (
            state["phases"]["gate-3-execute"]["artifact"]
            == "pytest tests/ -q -> exit 1 (2 failed)"
        ), "the failing run must be on record, not hidden"

        _checkpoint_turns(tmp_path, 4)  # G3 retry with exit 0
        state = _global_state(tmp_path)
        assert (
            state["phases"]["gate-3-execute"]["artifact"]
            == "pytest tests/ -q -> exit 0 (48 passed)"
        )

    def test_delivery_state_after_gate4(self, tmp_path):
        _checkpoint_turns(tmp_path, 5)
        state = _global_state(tmp_path)
        assert state["workflow"] == "evidence-flow"
        for gate in ("gate-1-context", "gate-2-plan", "gate-3-execute"):
            assert state["phases"][gate]["status"] == "completed"
        assert state["phases"]["gate-4-review"]["status"] == "in_progress"

    def test_interrupted_session_resumes_at_correct_gate(self, tmp_path):
        # Interruption right after the induced failure (rate limit,
        # context exhaustion): the next session must resume at gate 3
        # with the failing evidence visible, not restart the flow.
        # SessionStart owns meta creation in production — seed it here.
        SessionStore(SESSION).save_meta(
            SessionMeta(
                session_id=SESSION,
                project="arka-os",
                started_at="2026-07-09T14:00:00+00:00",
            )
        )
        _checkpoint_turns(tmp_path, 3)
        ctx = rehydrate_session(SESSION)
        assert ctx is not None
        assert ctx.workflow_snapshot is not None
        assert ctx.workflow_snapshot.current_phase == "gate-3-execute"
        assert ctx.workflow_snapshot.artifacts == [
            "pytest tests/ -q -> exit 1 (2 failed)"
        ]
        assert "gate-4-review" in ctx.pending_items

    def test_evidence_floor_blocks_approved_over_fail(self):
        # The Quality Gate cannot round an induced failure up to
        # APPROVED — reach_verdict raises on evidence_overall='fail'.
        engine = ReviewWorkflowEngine()
        workflow = engine.submit(
            deliverable_title="e2e deliverable",
            deliverable_type="code",
            submitter="paulo",
        )
        with pytest.raises(ValueError, match="evidence floor"):
            engine.reach_verdict(
                workflow.id, Verdict.APPROVED, evidence_overall="fail"
            )
        result = engine.reach_verdict(
            workflow.id, Verdict.REJECTED, evidence_overall="fail"
        )
        assert result.success
