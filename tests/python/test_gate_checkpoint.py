"""Tests for core.workflow.gate_checkpoint (v4.1.0 evidence flow).

All filesystem writes are redirected to tmp_path via HOME monkeypatching —
never touch the real ~/.arkaos (constitution: destructive primitives are
stubbed in cross-cutting tests).
"""

import json
from pathlib import Path

import pytest

from core.workflow import gate_checkpoint
from core.workflow.gate_checkpoint import (
    GATES,
    checkpoint,
    extract_gate3_evidence,
    extract_latest_gate,
)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    yield


def _write_transcript(path: Path, assistant_texts: list[str]) -> Path:
    records = [{"role": "user", "content": "do the thing"}]
    records.extend(
        {"role": "assistant", "content": text} for text in assistant_texts
    )
    path.write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8"
    )
    return path


class TestExtraction:
    def test_no_markers_returns_none(self):
        assert extract_latest_gate(["plain prose", "more prose"]) is None

    def test_single_gate(self):
        assert extract_latest_gate(["[arka:gate:1] context"]) == 1

    def test_highest_gate_wins(self):
        messages = ["[arka:gate:1] a", "[arka:gate:3] b", "[arka:gate:2] c"]
        assert extract_latest_gate(messages) == 3

    def test_gate2_mid_window_survives_trailing_prose(self):
        # PR4 prerequisite #1: a plan presented mid-turn (gate:2) with a
        # trailing marker-less summary. Over the window this is still 2,
        # so plan_approval marks 'presented' — last-message-only missed it.
        window = [
            "[arka:gate:1] context",
            "[arka:gate:2] plan: scope, files, verify",
            "Here is the plan above — waiting for your approval.",
        ]
        assert extract_latest_gate(window) == 2
        assert extract_latest_gate([window[-1]]) is None  # old behaviour

    def test_case_insensitive(self):
        assert extract_latest_gate(["[ARKA:GATE:4] review"]) == 4

    def test_gate3_evidence_captured(self):
        messages = [
            "[arka:gate:3] evidence: pytest tests/python -q -> exit 0 (4521 passed)"
        ]
        evidence = extract_gate3_evidence(messages)
        assert evidence == "pytest tests/python -q -> exit 0 (4521 passed)"

    def test_gate3_without_evidence_line(self):
        assert extract_gate3_evidence(["[arka:gate:3] implementing"]) is None


class TestCheckpoint:
    def test_no_gates_is_noop(self, tmp_path):
        transcript = _write_transcript(tmp_path / "t.jsonl", ["just prose"])
        assert checkpoint(str(transcript), "sess-1") is None
        assert not (tmp_path / ".arkaos" / "workflow-state.json").exists()

    def test_persists_global_state(self, tmp_path):
        transcript = _write_transcript(
            tmp_path / "t.jsonl",
            ["[arka:gate:1] ctx", "[arka:gate:2] plan"],
        )
        result = checkpoint(str(transcript), "sess-1")
        assert result == {
            "gate": 2,
            "current_phase": "gate-2-plan",
            "evidence": None,
        }
        state = json.loads(
            (tmp_path / ".arkaos" / "workflow-state.json").read_text(encoding="utf-8")
        )
        assert state["workflow"] == "evidence-flow"
        assert state["phases"]["gate-1-context"]["status"] == "completed"
        assert state["phases"]["gate-2-plan"]["status"] == "in_progress"
        assert state["phases"]["gate-3-execute"]["status"] == "pending"

    def test_persists_session_snapshot_for_rehydrator(self, tmp_path):
        transcript = _write_transcript(
            tmp_path / "t.jsonl",
            ["[arka:gate:3] evidence: pytest -q -> exit 0 (12 passed)"],
        )
        checkpoint(str(transcript), "sess-abc")
        snapshot_file = (
            tmp_path / ".arkaos" / "sessions" / "sess-abc" / "workflow-state.json"
        )
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert snapshot["workflow_name"] == "evidence-flow"
        assert snapshot["current_phase"] == "gate-3-execute"
        assert snapshot["artifacts"] == ["pytest -q -> exit 0 (12 passed)"]

    def test_gate3_evidence_stored_as_artifact(self, tmp_path):
        transcript = _write_transcript(
            tmp_path / "t.jsonl",
            ["[arka:gate:3] evidence: npm test -> exit 0 (all green)"],
        )
        checkpoint(str(transcript), "sess-1")
        state = json.loads(
            (tmp_path / ".arkaos" / "workflow-state.json").read_text(encoding="utf-8")
        )
        assert (
            state["phases"]["gate-3-execute"]["artifact"]
            == "npm test -> exit 0 (all green)"
        )

    def test_unsafe_session_id_skips_session_store(self, tmp_path):
        transcript = _write_transcript(
            tmp_path / "t.jsonl", ["[arka:gate:1] ctx"]
        )
        result = checkpoint(str(transcript), "../../evil")
        assert result is not None  # global state still persisted
        assert not (tmp_path / ".arkaos" / "sessions").exists()

    def test_missing_transcript_never_raises(self):
        assert checkpoint("/nonexistent/t.jsonl", "sess-1") is None

    def test_gate_names_are_stable(self):
        assert GATES == (
            "gate-1-context",
            "gate-2-plan",
            "gate-3-execute",
            "gate-4-review",
        )
