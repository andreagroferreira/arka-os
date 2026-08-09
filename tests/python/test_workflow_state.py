"""Tests for workflow state tracker."""

import json
from pathlib import Path

import pytest

from core.workflow.state import (
    add_violation,
    clear_workflow,
    get_state,
    init_workflow,
    is_phase_completed,
    set_branch,
    update_phase,
)

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
        init_workflow("dev/feature", "/tmp/proj", ["context", "spec", "implementation"])
        path = tmp_path / STATE_FILE_NAME
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
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


# ─── Gate Economy PR-9: per-project scoping, cap, batch write ──────────

# Captured at import time, BEFORE the autouse fixture patches it.
from core.workflow.state import _state_path as _real_state_path  # noqa: E402


class TestProjectScoping:
    """These tests exercise the REAL _state_path (the autouse fixture
    replaces it module-wide, so it is restored explicitly here)."""

    def _real(self, monkeypatch, tmp_path):
        import core.workflow.state as st

        monkeypatch.setattr(st, "_state_path", _real_state_path)
        monkeypatch.setattr(st.Path, "home", lambda: tmp_path)
        return st

    def test_state_path_is_per_project(self, tmp_path, monkeypatch):
        st = self._real(monkeypatch, tmp_path)
        proj_a = tmp_path / "proj-a"
        proj_b = tmp_path / "proj-b"
        proj_a.mkdir()
        proj_b.mkdir()
        monkeypatch.chdir(proj_a)
        path_a = st._state_path()
        monkeypatch.chdir(proj_b)
        path_b = st._state_path()
        assert path_a != path_b
        assert path_a.parent == path_b.parent
        assert path_a.parent.name == "workflow-state"

    def test_same_cwd_is_stable(self, tmp_path, monkeypatch):
        st = self._real(monkeypatch, tmp_path)
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        assert st._state_path() == st._state_path()

    def test_legacy_global_file_is_dropped_on_read(
        self, tmp_path, monkeypatch
    ):
        import core.workflow.state as st

        monkeypatch.setattr(st.Path, "home", lambda: tmp_path)
        legacy = tmp_path / ".arkaos" / "workflow-state.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            json.dumps({"violations": [{"rule": "spec-driven"}] * 217}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            st, "_LEGACY_STATE_PATH", legacy
        )
        assert st._read() is None
        assert not legacy.exists()


class TestViolationCap:
    def test_violations_capped_at_max(self):
        from core.workflow.state import MAX_VIOLATIONS

        init_workflow("dev/feature", "/tmp/p", ["spec"])
        for n in range(MAX_VIOLATIONS + 25):
            add_violation("spec-driven", f"v{n}")
        state = get_state()
        assert len(state["violations"]) == MAX_VIOLATIONS
        assert state["violations"][-1]["detail"] == (
            f"v{MAX_VIOLATIONS + 24}"
        )
        assert state["violations"][0]["detail"] == "v25"


class TestUpdatePhasesBatch:
    def test_updates_all_phases_in_one_call(self):
        from core.workflow.state import update_phases

        init_workflow("evidence-flow", "/tmp/p", ["g1", "g2", "g3"])
        update_phases(
            {"g1": "completed", "g2": "in_progress", "g3": "pending"},
            artifacts={"g2": "pytest -q -> exit 0"},
        )
        state = get_state()
        assert state["phases"]["g1"]["status"] == "completed"
        assert state["phases"]["g2"]["artifact"] == "pytest -q -> exit 0"
        assert state["phases"]["g3"]["status"] == "pending"

    def test_single_write_for_the_batch(self, monkeypatch):
        import core.workflow.state as st

        init_workflow("evidence-flow", "/tmp/p", ["g1", "g2", "g3", "g4"])
        writes = {"n": 0}
        real_write = st._write

        def counting_write(state):
            writes["n"] += 1
            return real_write(state)

        monkeypatch.setattr(st, "_write", counting_write)
        st.update_phases(
            {"g1": "completed", "g2": "completed",
             "g3": "in_progress", "g4": "pending"}
        )
        assert writes["n"] == 1

    def test_invalid_status_rejected(self):
        from core.workflow.state import update_phases

        init_workflow("evidence-flow", "/tmp/p", ["g1"])
        with pytest.raises(ValueError):
            update_phases({"g1": "nope"})

    def test_unknown_phase_rejected(self):
        from core.workflow.state import update_phases

        init_workflow("evidence-flow", "/tmp/p", ["g1"])
        with pytest.raises(ValueError):
            update_phases({"ghost": "completed"})


# ─── Gate Economy PR-9: spec-driven judged by disk, not phantom phase ──


class TestSpecDrivenGovernance:
    """The evidence-flow phase set has no "spec" phase; the old check
    appended a FALSE violation on every code edit (217 measured)."""

    def _state(self, phases):
        return {
            "workflow": "evidence-flow",
            "phases": {p: {"status": s} for p, s in phases.items()},
            "violations": [],
        }

    def _run(self, tmp_path, monkeypatch, state, specs_active=False):
        from core.hooks import post_tool_use as ptu

        project = tmp_path / "proj"
        spec_dir = project / ".arkaos" / "specs"
        spec_dir.mkdir(parents=True)
        if specs_active:
            (spec_dir / "feature.yaml").write_text(
                "status: approved\n", encoding="utf-8"
            )
        monkeypatch.chdir(project)
        captured = []
        monkeypatch.setattr(
            ptu, "_persist_violations", lambda entries: captured.extend(entries)
        ) if hasattr(ptu, "_persist_violations") else None
        return ptu, project, captured

    def test_evidence_flow_with_approved_spec_is_clean(
        self, tmp_path, monkeypatch
    ):
        from core.hooks.post_tool_use import _spec_driven_on_disk

        project = tmp_path / "proj"
        spec_dir = project / ".arkaos" / "specs"
        spec_dir.mkdir(parents=True)
        (spec_dir / "feature.yaml").write_text(
            "status: approved\n", encoding="utf-8"
        )
        monkeypatch.chdir(project)
        violated, msg = _spec_driven_on_disk("Edit", "core/x.py")
        assert violated is False
        assert msg == ""

    def test_evidence_flow_without_spec_flags_once_per_edit(
        self, tmp_path, monkeypatch
    ):
        from core.hooks.post_tool_use import _spec_driven_on_disk

        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)
        violated, msg = _spec_driven_on_disk("Edit", "core/x.py")
        assert violated is True
        assert "spec-driven" in msg

    def test_non_code_file_never_flags(self, tmp_path, monkeypatch):
        from core.hooks.post_tool_use import _spec_driven_on_disk

        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)
        violated, _ = _spec_driven_on_disk("Edit", "docs/guide.md")
        assert violated is False


class TestDetectRuleViolationsBranch:
    """Branch-level: the governance block picks the phase check ONLY
    when the workflow's phase set actually has a "spec" phase; the
    evidence-flow judges by disk (Gate Economy PR-9 — 217 false
    violations came from the wrong branch)."""

    def _evidence_state(self):
        return {
            "workflow": "evidence-flow",
            "phases": {
                "gate-1-context": {"status": "completed"},
                "gate-2-plan": {"status": "in_progress"},
            },
            "violations": [],
        }

    def _input(self, project, file_path):
        return {
            "tool_name": "Edit",
            "cwd": str(project),
            "tool_input": {"file_path": str(project / file_path)},
        }

    def _project(self, tmp_path, monkeypatch, with_spec):
        project = tmp_path / "proj"
        (project / "core").mkdir(parents=True)
        if with_spec:
            spec_dir = project / ".arkaos" / "specs"
            spec_dir.mkdir(parents=True)
            (spec_dir / "feature.yaml").write_text(
                "status: approved\n", encoding="utf-8"
            )
        monkeypatch.chdir(project)
        return project

    def test_evidence_flow_with_spec_on_disk_is_clean(
        self, tmp_path, monkeypatch
    ):
        from core.hooks import post_tool_use as ptu

        project = self._project(tmp_path, monkeypatch, with_spec=True)
        monkeypatch.setattr(
            ptu, "_workflow_state", lambda: self._evidence_state()
        )
        msg, persist = ptu._detect_rule_violations(
            self._input(project, "core/x.py")
        )
        assert msg == ""
        assert persist == []

    def test_evidence_flow_without_spec_flags_by_disk(
        self, tmp_path, monkeypatch
    ):
        from core.hooks import post_tool_use as ptu

        project = self._project(tmp_path, monkeypatch, with_spec=False)
        monkeypatch.setattr(
            ptu, "_workflow_state", lambda: self._evidence_state()
        )
        msg, persist = ptu._detect_rule_violations(
            self._input(project, "core/x.py")
        )
        assert "spec-driven" in msg
        assert persist and persist[0][0] == "spec-driven"

    def test_department_workflow_keeps_phase_semantics(
        self, tmp_path, monkeypatch
    ):
        from core.hooks import post_tool_use as ptu

        project = self._project(tmp_path, monkeypatch, with_spec=True)
        dept_state = {
            "workflow": "dev/feature",
            "phases": {
                "spec": {"status": "pending"},
                "implementation": {"status": "pending"},
            },
            "violations": [],
        }
        monkeypatch.setattr(ptu, "_workflow_state", lambda: dept_state)
        msg, persist = ptu._detect_rule_violations(
            self._input(project, "core/x.py")
        )
        # phase pending → violation even with a spec on disk: the
        # department workflow's own gate still owns its semantics
        assert "spec-driven" in msg
        assert persist[0][0] == "spec-driven"
