import pytest
import yaml
from core.forge.schema import ForgePlan, ForgeContext, PlanPhase, ExecutionPath, ExecutionPathType
from core.forge.handoff import select_execution_path, generate_workflow_yaml


def _ctx():
    return ForgeContext(repo="arka-os", branch="master", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test")


class TestSelectExecutionPath:
    def test_single_phase_skill(self):
        assert select_execution_path([PlanPhase(name="Fix", department="dev")]).type == ExecutionPathType.SKILL

    def test_two_phases_workflow(self):
        phases = [PlanPhase(name="A", department="dev"), PlanPhase(name="B", department="dev")]
        assert select_execution_path(phases).type == ExecutionPathType.WORKFLOW

    def test_three_phases_workflow(self):
        phases = [PlanPhase(name=f"P{i}", department="dev") for i in range(3)]
        assert select_execution_path(phases).type == ExecutionPathType.WORKFLOW

    def test_four_phases_enterprise(self):
        phases = [PlanPhase(name=f"P{i}", department="dev") for i in range(4)]
        assert select_execution_path(phases).type == ExecutionPathType.ENTERPRISE_WORKFLOW

    def test_multi_dept_enterprise(self):
        phases = [PlanPhase(name="A", department="dev"), PlanPhase(name="B", department="ops")]
        assert select_execution_path(phases).type == ExecutionPathType.ENTERPRISE_WORKFLOW

    def test_departments_included(self):
        phases = [PlanPhase(name="A", department="dev"), PlanPhase(name="B", department="ops")]
        path = select_execution_path(phases)
        assert "dev" in path.departments and "ops" in path.departments


class TestGenerateWorkflowYaml:
    def test_valid_yaml(self):
        plan = ForgePlan(id="forge-test", name="Test", context=_ctx(),
            plan_phases=[PlanPhase(name="Schema", department="dev", agents=["backend-dev"], deliverables=["schema.py"], acceptance_criteria=["Validates"]),
                PlanPhase(name="QG", department="quality", depends_on=["Schema"])])
        data = yaml.safe_load(generate_workflow_yaml(plan))
        assert data["name"] == "forge-test" and len(data["phases"]) == 2

    def test_preserves_depends_on(self):
        plan = ForgePlan(id="forge-dep", name="Dep", context=_ctx(),
            plan_phases=[PlanPhase(name="P1", department="dev"), PlanPhase(name="P2", department="dev", depends_on=["P1"])])
        data = yaml.safe_load(generate_workflow_yaml(plan))
        assert data["phases"][1]["depends_on"] == ["P1"]

    def test_quality_gate_flag(self):
        plan = ForgePlan(id="forge-qg", name="QG", context=_ctx(), plan_phases=[PlanPhase(name="P1", department="dev")])
        data = yaml.safe_load(generate_workflow_yaml(plan))
        assert data["quality_gate_required"] is True
