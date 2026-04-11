"""Tests for workflow state tracker."""

import json
from pathlib import Path

import pytest

from core.workflow.state import init_workflow, get_state, clear_workflow
from core.workflow.state import update_phase, set_branch, add_violation, is_phase_completed

STATE_FILE_NAME = "workflow-state.json"


@pytest.fixture(autouse=True)
def _use_tmp_state(tmp_path, monkeypatch):
    """Redirect state file to tmp_path for all tests."""
    monkeypatch.setattr(
        "core.workflow.state._state_path",
        lambda: tmp_path / STATE_FILE_NAME,
    )


class TestInitWorkflow:
    def test_creates_state_file(self, tmp_path: Path) -> None:
        result = init_workflow("dev/feature", "/tmp/proj", ["context", "spec", "implementation"])
        path = tmp_path / STATE_FILE_NAME
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["workflow"] == "dev/feature"
        assert data["project"] == "/tmp/proj"

    def test_phases_initialized_as_pending(self) -> None:
        result = init_workflow("dev/feature", "/tmp/proj", ["context", "spec"])
        for phase in result["phases"].values():
            assert phase["status"] == "pending"

    def test_session_id_is_uuid(self) -> None:
        import uuid
        result = init_workflow("dev/fix", "/tmp/p", ["context"])
        uuid.UUID(result["session_id"], version=4)

    def test_overwrites_existing_state(self) -> None:
        init_workflow("dev/feature", "/tmp/a", ["context"])
        result = init_workflow("dev/fix", "/tmp/b", ["spec"])
        assert result["workflow"] == "dev/fix"
        assert result["project"] == "/tmp/b"


class TestGetState:
    def test_returns_none_when_no_file(self) -> None:
        assert get_state() is None

    def test_returns_state_after_init(self) -> None:
        init_workflow("dev/feature", "/tmp/proj", ["context", "spec"])
        state = get_state()
        assert state is not None
        assert state["workflow"] == "dev/feature"
        assert len(state["phases"]) == 2


class TestClearWorkflow:
    def test_removes_state_file(self, tmp_path: Path) -> None:
        init_workflow("dev/feature", "/tmp/proj", ["context"])
        clear_workflow()
        assert not (tmp_path / STATE_FILE_NAME).exists()

    def test_clear_when_no_file_is_noop(self) -> None:
        clear_workflow()  # should not raise


class TestUpdatePhase:
    def test_sets_phase_status(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context", "spec"])
        result = update_phase("context", "in_progress")
        assert result["phases"]["context"]["status"] == "in_progress"
        assert "at" in result["phases"]["context"]

    def test_completed_records_timestamp(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["spec"])
        result = update_phase("spec", "completed")
        assert result["phases"]["spec"]["status"] == "completed"
        assert result["phases"]["spec"]["at"]

    def test_stores_artifact(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["spec"])
        result = update_phase("spec", "completed", artifact="docs/spec.md")
        assert result["phases"]["spec"]["artifact"] == "docs/spec.md"

    def test_rejects_invalid_status(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        with pytest.raises(ValueError, match="Invalid status"):
            update_phase("context", "cancelled")

    def test_rejects_unknown_phase(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        with pytest.raises(ValueError, match="Unknown phase"):
            update_phase("nonexistent", "completed")

    def test_raises_when_no_workflow(self) -> None:
        with pytest.raises(RuntimeError, match="No active workflow"):
            update_phase("context", "completed")


class TestSetBranch:
    def test_sets_branch(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = set_branch("feature/add-auth")
        assert result["branch"] == "feature/add-auth"


class TestAddViolation:
    def test_appends_violation(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = add_violation("spec-driven", "Code edited without spec")
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "spec-driven"
        assert result["violations"][0]["detail"] == "Code edited without spec"
        assert "at" in result["violations"][0]

    def test_records_tool_and_file(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = add_violation("spec-driven", "Code edited", tool="Edit", file="src/a.py")
        v = result["violations"][0]
        assert v["tool"] == "Edit"
        assert v["file"] == "src/a.py"

    def test_multiple_violations_accumulate(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        add_violation("rule-a", "detail-a")
        result = add_violation("rule-b", "detail-b")
        assert len(result["violations"]) == 2


class TestIsPhaseCompleted:
    def test_returns_true_when_completed(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        update_phase("context", "completed")
        assert is_phase_completed("context") is True

    def test_returns_false_when_pending(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        assert is_phase_completed("context") is False

    def test_returns_false_when_no_workflow(self) -> None:
        assert is_phase_completed("context") is False
