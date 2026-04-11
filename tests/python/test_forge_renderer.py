import pytest
from core.forge.schema import (
    ForgePlan, ForgeContext, ForgeTier, ComplexityScore, ComplexityDimensions,
    CriticVerdict, RejectedElement, IdentifiedRisk, RiskSeverity,
    PlanPhase, ExecutionPath, ExecutionPathType,
)
from core.forge.renderer import render_complexity, render_critic_summary, render_plan_overview, render_terminal


def _make_complexity(score=72, tier="deep"):
    return ComplexityScore(score=score, tier=ForgeTier(tier),
        dimensions=ComplexityDimensions(scope=85, dependencies=60, ambiguity=55, risk=70, novelty=90))


class TestRenderComplexity:
    def test_contains_score(self):
        assert "72" in render_complexity(_make_complexity())

    def test_contains_tier(self):
        output = render_complexity(_make_complexity())
        assert "Deep" in output or "deep" in output

    def test_contains_dimension_names(self):
        output = render_complexity(_make_complexity())
        assert "Scope" in output and "Risk" in output and "Novelty" in output

    def test_contains_bar_chars(self):
        assert any(c in render_complexity(_make_complexity()) for c in ("█", "░"))


class TestRenderCriticSummary:
    def test_contains_confidence(self):
        v = CriticVerdict(synthesis={"a": ["x"]}, rejected_elements=[RejectedElement(element="e", reason="r")],
            risks=[IdentifiedRisk(risk="r", mitigation="m", severity=RiskSeverity.LOW)], confidence=0.82)
        assert "0.82" in render_critic_summary(v)

    def test_contains_rejected_count(self):
        v = CriticVerdict(rejected_elements=[RejectedElement(element="e1", reason="r1"), RejectedElement(element="e2", reason="r2")],
            risks=[IdentifiedRisk(risk="r", mitigation="m")], confidence=0.7)
        assert "2" in render_critic_summary(v)


class TestRenderPlanOverview:
    def test_contains_phase_names(self):
        phases = [PlanPhase(name="Core Schema", department="dev"), PlanPhase(name="Hook Integration", department="ops")]
        output = render_plan_overview(phases, ExecutionPath(type=ExecutionPathType.WORKFLOW, target="wf.yaml"))
        assert "Core Schema" in output and "Hook Integration" in output

    def test_contains_departments(self):
        output = render_plan_overview([PlanPhase(name="P1", department="dev")], ExecutionPath(type=ExecutionPathType.SKILL, target="arka-dev"))
        assert "dev" in output


class TestRenderTerminal:
    def test_full_render(self):
        plan = ForgePlan(id="forge-test", name="Test Plan",
            context=ForgeContext(repo="arka-os", branch="master", commit_at_forge="abc", arkaos_version="2.14.0", prompt="Build"),
            complexity=_make_complexity(),
            critic=CriticVerdict(synthesis={"a": ["x"]}, rejected_elements=[RejectedElement(element="e", reason="r")],
                risks=[IdentifiedRisk(risk="r", mitigation="m", severity=RiskSeverity.LOW)], confidence=0.75),
            plan_phases=[PlanPhase(name="Phase 1", department="dev")],
            execution_path=ExecutionPath(type=ExecutionPathType.WORKFLOW, target="wf.yaml"))
        output = render_terminal(plan)
        assert "FORGE" in output and "72" in output and "0.75" in output and "Phase 1" in output
