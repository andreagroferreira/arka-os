"""Tests that all workflow YAML files load and validate correctly."""

import pytest
from pathlib import Path

from core.workflow.loader import load_workflow
from core.workflow.schema import GateType, WorkflowTier


DEPARTMENTS_DIR = Path(__file__).parent.parent.parent / "departments"
WORKFLOW_FILES = sorted(DEPARTMENTS_DIR.glob("*/workflows/*.yaml"))


class TestAllWorkflowsLoad:
    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda f: f.stem)
    def test_workflow_loads(self, wf_file):
        wf = load_workflow(wf_file)
        assert wf.id
        assert wf.name
        assert wf.department

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda f: f.stem)
    def test_workflow_has_phases(self, wf_file):
        wf = load_workflow(wf_file)
        min_phases = 2 if wf.tier.value == "specialist" else 3
        assert len(wf.phases) >= min_phases, f"{wf.id} ({wf.tier.value}) has less than {min_phases} phases"

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda f: f.stem)
    def test_workflow_has_quality_gate(self, wf_file):
        wf = load_workflow(wf_file)
        if wf.quality_gate_required:
            qg_phases = [p for p in wf.phases if p.gate.type == GateType.QUALITY_GATE]
            assert len(qg_phases) >= 1, f"{wf.id} requires quality gate but has none"

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda f: f.stem)
    def test_every_phase_has_agents(self, wf_file):
        wf = load_workflow(wf_file)
        for phase in wf.phases:
            assert len(phase.agents) >= 1, f"{wf.id} phase {phase.id} has no agents"

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda f: f.stem)
    def test_quality_gate_has_marta(self, wf_file):
        wf = load_workflow(wf_file)
        for phase in wf.phases:
            if phase.gate.type == GateType.QUALITY_GATE:
                agent_ids = [a.agent_id for a in phase.agents]
                assert "cqo-marta" in agent_ids, f"{wf.id} QG phase missing Marta"


class TestWorkflowCoverage:
    def test_total_workflows(self):
        assert len(WORKFLOW_FILES) >= 7, f"Expected 7+ workflows, found {len(WORKFLOW_FILES)}"

    def test_enterprise_workflows_exist(self):
        enterprise = []
        for f in WORKFLOW_FILES:
            wf = load_workflow(f)
            if wf.tier == WorkflowTier.ENTERPRISE:
                enterprise.append(wf.id)
        assert len(enterprise) >= 5, f"Expected 5+ enterprise workflows, found {len(enterprise)}"

    def test_departments_with_workflows(self):
        depts = set()
        for f in WORKFLOW_FILES:
            wf = load_workflow(f)
            depts.add(wf.department)
        assert len(depts) >= 6, f"Expected 6+ departments with workflows, found {len(depts)}"

    def test_all_workflows_have_final_output_phase(self):
        """Every workflow ends with a delivery/documentation/output phase."""
        for f in WORKFLOW_FILES:
            wf = load_workflow(f)
            last_phase = wf.phases[-1].id
            valid_finals = {"delivery", "documentation", "actions"}
            assert last_phase in valid_finals, f"{wf.id} last phase '{last_phase}' not a final phase"
