"""Tests for The Forge — schema enums and base complexity models."""

import pytest

from core.forge.schema import (
    ForgeTier,
    ForgeStatus,
    ExplorerLens,
    RiskSeverity,
    ExecutionPathType,
    ComplexityDimensions,
    ComplexityScore,
    KeyDecision,
    PhaseDeliverable,
    ExplorerApproach,
    RejectedElement,
    IdentifiedRisk,
    CriticVerdict,
    ForgeContext,
    PlanPhase,
    ExecutionPath,
    ForgeGovernance,
    ForgePlan,
)


# --- ForgeTier ---

class TestForgeTier:
    def test_values_exist(self) -> None:
        assert ForgeTier.SHALLOW == "shallow"
        assert ForgeTier.STANDARD == "standard"
        assert ForgeTier.DEEP == "deep"

    def test_is_string_enum(self) -> None:
        assert isinstance(ForgeTier.SHALLOW, str)

    def test_all_three_tiers(self) -> None:
        tiers = [t.value for t in ForgeTier]
        assert set(tiers) == {"shallow", "standard", "deep"}


# --- ForgeStatus ---

class TestForgeStatus:
    def test_all_lifecycle_values_exist(self) -> None:
        values = {s.value for s in ForgeStatus}
        assert "draft" in values
        assert "reviewing" in values
        assert "approved" in values
        assert "executing" in values
        assert "completed" in values
        assert "rejected" in values
        assert "cancelled" in values
        assert "archived" in values

    def test_is_string_enum(self) -> None:
        assert isinstance(ForgeStatus.DRAFT, str)

    def test_count(self) -> None:
        assert len(ForgeStatus) == 8


# --- ExplorerLens ---

class TestExplorerLens:
    def test_values_exist(self) -> None:
        assert ExplorerLens.PRAGMATIC == "pragmatic"
        assert ExplorerLens.ARCHITECTURAL == "architectural"
        assert ExplorerLens.CONTRARIAN == "contrarian"

    def test_is_string_enum(self) -> None:
        assert isinstance(ExplorerLens.PRAGMATIC, str)

    def test_all_three_lenses(self) -> None:
        lenses = [l.value for l in ExplorerLens]
        assert set(lenses) == {"pragmatic", "architectural", "contrarian"}


# --- RiskSeverity ---

class TestRiskSeverity:
    def test_values_exist(self) -> None:
        assert RiskSeverity.LOW == "low"
        assert RiskSeverity.MEDIUM == "medium"
        assert RiskSeverity.HIGH == "high"

    def test_is_string_enum(self) -> None:
        assert isinstance(RiskSeverity.LOW, str)


# --- ExecutionPathType ---

class TestExecutionPathType:
    def test_values_exist(self) -> None:
        assert ExecutionPathType.SKILL == "skill"
        assert ExecutionPathType.WORKFLOW == "workflow"
        assert ExecutionPathType.ENTERPRISE_WORKFLOW == "enterprise_workflow"

    def test_is_string_enum(self) -> None:
        assert isinstance(ExecutionPathType.SKILL, str)


# --- ComplexityDimensions ---

class TestComplexityDimensions:
    def test_create_with_valid_values(self) -> None:
        dims = ComplexityDimensions(
            scope=50,
            dependencies=30,
            ambiguity=70,
            risk=20,
            novelty=60,
        )
        assert dims.scope == 50
        assert dims.dependencies == 30
        assert dims.ambiguity == 70
        assert dims.risk == 20
        assert dims.novelty == 60

    def test_clamp_above_100(self) -> None:
        dims = ComplexityDimensions(
            scope=150,
            dependencies=200,
            ambiguity=101,
            risk=999,
            novelty=100,
        )
        assert dims.scope == 100
        assert dims.dependencies == 100
        assert dims.ambiguity == 100
        assert dims.risk == 100
        assert dims.novelty == 100

    def test_clamp_below_0(self) -> None:
        dims = ComplexityDimensions(
            scope=-10,
            dependencies=-1,
            ambiguity=-50,
            risk=-100,
            novelty=0,
        )
        assert dims.scope == 0
        assert dims.dependencies == 0
        assert dims.ambiguity == 0
        assert dims.risk == 0
        assert dims.novelty == 0

    def test_boundary_values_unchanged(self) -> None:
        dims = ComplexityDimensions(
            scope=0,
            dependencies=100,
            ambiguity=50,
            risk=1,
            novelty=99,
        )
        assert dims.scope == 0
        assert dims.dependencies == 100
        assert dims.ambiguity == 50
        assert dims.risk == 1
        assert dims.novelty == 99

    def test_defaults_to_zero(self) -> None:
        dims = ComplexityDimensions()
        assert dims.scope == 0
        assert dims.dependencies == 0
        assert dims.ambiguity == 0
        assert dims.risk == 0
        assert dims.novelty == 0


# --- ComplexityScore ---

class TestComplexityScore:
    def test_shallow_tier(self) -> None:
        score = ComplexityScore(
            score=20,
            tier=ForgeTier.SHALLOW,
            dimensions=ComplexityDimensions(scope=20, dependencies=15, ambiguity=10, risk=5, novelty=30),
        )
        assert score.score == 20
        assert score.tier == ForgeTier.SHALLOW

    def test_default_empty_lists(self) -> None:
        score = ComplexityScore(
            score=50,
            tier=ForgeTier.STANDARD,
            dimensions=ComplexityDimensions(),
        )
        assert score.similar_plans == []
        assert score.reused_patterns == []

    def test_similar_plans_populated(self) -> None:
        score = ComplexityScore(
            score=80,
            tier=ForgeTier.DEEP,
            dimensions=ComplexityDimensions(scope=80),
            similar_plans=["plan-abc", "plan-xyz"],
        )
        assert len(score.similar_plans) == 2
        assert "plan-abc" in score.similar_plans

    def test_reused_patterns_populated(self) -> None:
        score = ComplexityScore(
            score=60,
            tier=ForgeTier.STANDARD,
            dimensions=ComplexityDimensions(novelty=60),
            reused_patterns=["phase-gate", "quality-gate"],
        )
        assert "phase-gate" in score.reused_patterns

    def test_all_tiers_accepted(self) -> None:
        for tier in ForgeTier:
            score = ComplexityScore(
                score=50,
                tier=tier,
                dimensions=ComplexityDimensions(),
            )
            assert score.tier == tier


# --- ExplorerApproach ---

class TestExplorerApproach:
    def test_create_approach(self):
        approach = ExplorerApproach(explorer=ExplorerLens.PRAGMATIC, summary="Fast path")
        assert approach.explorer == ExplorerLens.PRAGMATIC

    def test_default_empty_lists(self):
        approach = ExplorerApproach(explorer=ExplorerLens.ARCHITECTURAL, summary="")
        assert approach.key_decisions == []
        assert approach.risks == []


# --- CriticVerdict ---

class TestCriticVerdict:
    def test_create_verdict(self):
        verdict = CriticVerdict(
            synthesis={"a": ["x"]},
            rejected_elements=[RejectedElement(element="e", reason="r")],
            risks=[IdentifiedRisk(risk="r", mitigation="m", severity=RiskSeverity.MEDIUM)],
            confidence=0.82,
        )
        assert verdict.confidence == 0.82

    def test_is_valid_true(self):
        v = CriticVerdict(
            rejected_elements=[RejectedElement(element="e", reason="r")],
            risks=[IdentifiedRisk(risk="r", mitigation="m")],
            confidence=0.5,
        )
        assert v.is_valid() is True

    def test_is_valid_false_no_rejected(self):
        v = CriticVerdict(risks=[IdentifiedRisk(risk="r", mitigation="m")])
        assert v.is_valid() is False

    def test_is_valid_false_no_risks(self):
        v = CriticVerdict(rejected_elements=[RejectedElement(element="e", reason="r")])
        assert v.is_valid() is False


# --- ForgeContext ---

class TestForgeContext:
    def test_create_context(self):
        ctx = ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test")
        assert ctx.context_refreshed is False


# --- PlanPhase ---

class TestPlanPhase:
    def test_create_phase(self):
        p = PlanPhase(name="Schema", department="dev", deliverables=["schema.py"])
        assert p.department == "dev"

    def test_default_empty_context(self):
        p = PlanPhase(name="P", department="dev")
        assert p.context_from_forge == {}


# --- ForgePlan ---

class TestForgePlan:
    def test_create_minimal(self):
        plan = ForgePlan(
            id="forge-test", name="Test",
            context=ForgeContext(repo="t", branch="m", commit_at_forge="a", arkaos_version="2.14.0", prompt="p"),
        )
        assert plan.status == ForgeStatus.DRAFT
        assert plan.version == 1
        assert plan.approved_at is None

    def test_full_plan(self):
        plan = ForgePlan(
            id="forge-full", name="Full",
            context=ForgeContext(repo="arka-os", branch="master", commit_at_forge="b42", arkaos_version="2.14.0", prompt="build"),
            complexity=ComplexityScore(score=72, tier=ForgeTier.DEEP,
                dimensions=ComplexityDimensions(scope=85, dependencies=60, ambiguity=55, risk=70, novelty=90)),
            approaches=[ExplorerApproach(explorer=ExplorerLens.PRAGMATIC, summary="Fast")],
            critic=CriticVerdict(
                synthesis={"a": ["elem"]},
                rejected_elements=[RejectedElement(element="x", reason="y")],
                risks=[IdentifiedRisk(risk="r", mitigation="m", severity=RiskSeverity.LOW)],
                confidence=0.82),
            plan_phases=[PlanPhase(name="P1", department="dev")],
            execution_path=ExecutionPath(type=ExecutionPathType.ENTERPRISE_WORKFLOW, target="wf.yaml", departments=["dev", "ops"]),
            governance=ForgeGovernance(constitution_check="passed", quality_gate_required=True, branch_strategy="feature/forge"),
        )
        assert plan.complexity.tier == ForgeTier.DEEP
        assert plan.critic.confidence == 0.82
