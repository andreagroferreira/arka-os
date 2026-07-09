"""Tests for the YAML workflow schema and loader."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from core.workflow.schema import (
    Workflow, Phase, Gate, GateType, PhaseStatus,
    AgentAssignment, WorkflowTier,
)
from core.workflow.loader import load_workflow


# --- Fixtures ---

def make_phase(id: str, name: str, agents: list[str] | None = None, **kwargs) -> Phase:
    agent_list = [AgentAssignment(agent_id=a) for a in (agents or ["agent-1"])]
    return Phase(id=id, name=name, agents=agent_list, **kwargs)


def make_workflow(phases: list[Phase] | None = None, **kwargs) -> Workflow:
    defaults = {
        "id": "test-workflow",
        "name": "Test Workflow",
        "department": "dev",
        "phases": phases or [
            make_phase("p1", "Phase 1"),
            make_phase("p2", "Phase 2"),
            make_phase("p3", "Phase 3"),
        ],
    }
    defaults.update(kwargs)
    return Workflow(**defaults)


# --- Schema Tests ---

class TestWorkflowSchema:
    def test_create_workflow(self):
        wf = make_workflow()
        assert wf.id == "test-workflow"
        assert len(wf.phases) == 3
        assert wf.status == PhaseStatus.PENDING

    def test_get_current_phase(self):
        wf = make_workflow()
        phase = wf.get_current_phase()
        assert phase is not None
        assert phase.id == "p1"

    def test_get_phase_by_id(self):
        wf = make_workflow()
        phase = wf.get_phase_by_id("p2")
        assert phase is not None
        assert phase.name == "Phase 2"

    def test_get_phase_by_id_not_found(self):
        wf = make_workflow()
        assert wf.get_phase_by_id("nonexistent") is None

    def test_all_phases_complete(self):
        wf = make_workflow()
        assert not wf.all_phases_complete()
        for phase in wf.phases:
            phase.status = PhaseStatus.COMPLETED
        assert wf.all_phases_complete()

    def test_skipped_counts_as_complete(self):
        wf = make_workflow()
        wf.phases[0].status = PhaseStatus.COMPLETED
        wf.phases[1].status = PhaseStatus.SKIPPED
        wf.phases[2].status = PhaseStatus.COMPLETED
        assert wf.all_phases_complete()

    def test_next_phase(self):
        wf = make_workflow()
        wf.phases[0].status = PhaseStatus.COMPLETED
        next_p = wf.next_phase()
        assert next_p is not None
        assert next_p.id == "p2"

    def test_workflow_tiers(self):
        wf = make_workflow(tier=WorkflowTier.ENTERPRISE)
        assert wf.tier == WorkflowTier.ENTERPRISE


class TestPhaseModelOverride:
    def test_model_override_opus(self):
        phase = make_phase("p1", "Phase 1", model_override="opus")
        assert phase.model_override == "opus"

    def test_model_override_sonnet(self):
        phase = make_phase("p1", "Phase 1", model_override="sonnet")
        assert phase.model_override == "sonnet"

    def test_model_override_haiku(self):
        phase = make_phase("p1", "Phase 1", model_override="haiku")
        assert phase.model_override == "haiku"

    def test_model_override_default_none(self):
        phase = make_phase("p1", "Phase 1")
        assert phase.model_override is None

    def test_model_override_invalid_raises(self):
        with pytest.raises(ValidationError):
            make_phase("p1", "Phase 1", model_override="gpt-4")


class TestGate:
    def test_auto_gate(self):
        gate = Gate(type=GateType.AUTO)
        assert gate.type == GateType.AUTO

    def test_user_approval_gate(self):
        gate = Gate(type=GateType.USER_APPROVAL, description="Approve spec")
        assert gate.type == GateType.USER_APPROVAL

    def test_quality_gate(self):
        gate = Gate(type=GateType.QUALITY_GATE, required_verdict="APPROVED")
        assert gate.required_verdict == "APPROVED"


# --- YAML Loader Tests ---

class TestWorkflowLoader:
    def test_load_feature_workflow(self):
        path = Path(__file__).parent.parent.parent / "departments" / "dev" / "workflows" / "feature.yaml"
        if path.exists():
            wf = load_workflow(path)
            assert wf.id == "dev-feature"
            assert wf.department == "dev"
            assert wf.tier == WorkflowTier.ENTERPRISE
            assert wf.requires_branch is True
            assert wf.requires_spec is True
            assert wf.quality_gate_required is True
            assert len(wf.phases) == 9

            # Check quality gate phase exists
            qg = wf.get_phase_by_id("quality-gate")
            assert qg is not None
            assert qg.gate.type == GateType.QUALITY_GATE
            assert any(a.agent_id == "cqo-marta" for a in qg.agents)

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_workflow("/nonexistent/workflow.yaml")
