import pytest
from core.forge.schema import (
    ForgePlan, ForgeContext, ForgeTier, ComplexityScore, ComplexityDimensions,
    CriticVerdict, RejectedElement, IdentifiedRisk, RiskSeverity,
    PlanPhase, ExecutionPath, ExecutionPathType,
)
from core.forge.renderer import render_complexity, render_critic_summary, render_plan_overview, render_terminal, render_html, should_suggest_companion


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


class TestShouldSuggestCompanion:
    def test_shallow_none(self):
        assert should_suggest_companion(ForgeTier.SHALLOW) == "none"

    def test_standard_available(self):
        assert should_suggest_companion(ForgeTier.STANDARD) == "available"

    def test_deep_suggested(self):
        assert should_suggest_companion(ForgeTier.DEEP) == "suggested"


class TestRenderHtml:
    def test_valid_html(self):
        plan = ForgePlan(id="forge-html", name="HTML Test",
            context=ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test"),
            complexity=_make_complexity(score=50, tier="standard"))
        html = render_html(plan)
        assert "<!DOCTYPE html>" in html and "</html>" in html

    def test_contains_plan_name(self):
        plan = ForgePlan(id="forge-html", name="My Forge Plan",
            context=ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test"))
        assert "My Forge Plan" in render_html(plan)

    def test_contains_svg_radar(self):
        plan = ForgePlan(id="forge-html", name="Radar",
            context=ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test"),
            complexity=_make_complexity())
        assert "<svg" in render_html(plan)

    def test_under_50kb(self):
        plan = ForgePlan(id="forge-size", name="Size",
            context=ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test"),
            complexity=_make_complexity(),
            critic=CriticVerdict(synthesis={"a": ["x"] * 10},
                rejected_elements=[RejectedElement(element="e", reason="r")] * 5,
                risks=[IdentifiedRisk(risk="r", mitigation="m", severity=RiskSeverity.LOW)] * 5,
                confidence=0.8),
            plan_phases=[PlanPhase(name=f"Phase {i}", department="dev") for i in range(10)])
        assert len(render_html(plan).encode("utf-8")) < 50_000
