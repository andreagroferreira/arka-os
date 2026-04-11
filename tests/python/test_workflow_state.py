"""Tests for workflow state tracker."""

import json
from pathlib import Path

import pytest

from core.workflow.state import init_workflow, get_state, clear_workflow

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
