"""Tests for orchestration protocol."""

import pytest

from core.orchestration.protocol import (
    OrchestrationPattern,
    OrchestrationPhase,
    OrchestrationPlan,
    PatternType,
    PhaseHandoff,
)
from core.orchestration.patterns import PATTERNS, select_pattern


class TestPatternType:
    def test_all_four_patterns_defined(self):
        assert len(PatternType) == 4

    def test_pattern_values(self):
        assert PatternType.SOLO_SPRINT == "solo_sprint"
        assert PatternType.DOMAIN_DEEP_DIVE == "domain_deep_dive"
        assert PatternType.MULTI_AGENT_HANDOFF == "multi_agent_handoff"
        assert PatternType.SKILL_CHAIN == "skill_chain"


class TestPatterns:
    def test_all_patterns_registered(self):
        assert len(PATTERNS) == 4
        for pt in PatternType:
            assert pt in PATTERNS

    def test_each_pattern_has_required_fields(self):
        for pattern in PATTERNS.values():
            assert pattern.name
            assert pattern.description
            assert len(pattern.when_to_use) >= 2
            assert pattern.structure
            assert pattern.example
            assert len(pattern.anti_patterns) >= 2

    def test_solo_sprint(self):
        p = PATTERNS[PatternType.SOLO_SPRINT]
        assert "Sprint" in p.name
        assert "department" in p.description.lower() or "lead" in p.description.lower()

    def test_domain_deep_dive(self):
        p = PATTERNS[PatternType.DOMAIN_DEEP_DIVE]
        assert "Deep" in p.name
        assert "depth" in p.description.lower() or "stacked" in p.description.lower()

    def test_multi_agent_handoff(self):
        p = PATTERNS[PatternType.MULTI_AGENT_HANDOFF]
        assert "Handoff" in p.name
        assert "department" in p.description.lower() or "handoff" in p.description.lower()

    def test_skill_chain(self):
        p = PATTERNS[PatternType.SKILL_CHAIN]
        assert "Chain" in p.name
        assert "procedural" in p.description.lower() or "pipeline" in p.description.lower()


class TestPhaseHandoff:
    def test_create_handoff(self):
        h = PhaseHandoff(
            phase_number=1,
            phase_name="Strategy",
            decisions=["Enter B2B segment"],
            artifacts=["strategy.md"],
            next_department="dev",
            next_agent="paulo",
        )
        assert h.phase_number == 1
        assert len(h.decisions) == 1

    def test_to_context(self):
        h = PhaseHandoff(
            phase_number=1,
            phase_name="Strategy",
            decisions=["Enter B2B"],
            artifacts=["strategy.md"],
            open_questions=["Pricing model?"],
            next_department="dev",
            next_agent="paulo",
        )
        ctx = h.to_context()
        assert "Phase 1 (Strategy) complete" in ctx
        assert "Enter B2B" in ctx
        assert "strategy.md" in ctx
        assert "Pricing model?" in ctx
        assert "dev/paulo" in ctx

    def test_empty_handoff(self):
        h = PhaseHandoff(phase_number=1, phase_name="Test")
        ctx = h.to_context()
        assert "Phase 1 (Test) complete" in ctx
        assert "Decisions" not in ctx


class TestOrchestrationPlan:
    @pytest.fixture
    def plan(self):
        return OrchestrationPlan(
            objective="Launch SaaS product",
            pattern=PatternType.MULTI_AGENT_HANDOFF,
            constraints=["2-person team", "$5K budget"],
            success_criteria=["50 customers in 30 days"],
            phases=[
                OrchestrationPhase(number=1, name="Strategy", department="strategy", agent_id="strategy-director", skills=["bmc", "five-forces"]),
                OrchestrationPhase(number=2, name="Build", department="dev", agent_id="dev-lead", skills=["spec", "feature"]),
                OrchestrationPhase(number=3, name="Launch", department="marketing", agent_id="marketing-director", skills=["growth-plan"]),
            ],
        )

    def test_initial_state(self, plan):
        assert plan.current_phase == 0
        assert not plan.is_complete
        assert plan.progress_percent == 0

    def test_next_phase(self, plan):
        phase = plan.next_phase()
        assert phase is not None
        assert phase.name == "Strategy"
        assert phase.department == "strategy"

    def test_advance(self, plan):
        handoff = PhaseHandoff(phase_number=1, phase_name="Strategy", decisions=["Go B2B"])
        next_phase = plan.advance(handoff)
        assert next_phase is not None
        assert next_phase.name == "Build"
        assert plan.current_phase == 1
        assert plan.progress_percent == 33

    def test_complete_all_phases(self, plan):
        for i in range(3):
            plan.advance(PhaseHandoff(phase_number=i + 1, phase_name=f"Phase {i + 1}"))
        assert plan.is_complete
        assert plan.progress_percent == 100
        assert plan.next_phase() is None

    def test_empty_plan(self):
        plan = OrchestrationPlan(objective="Test", pattern=PatternType.SOLO_SPRINT)
        assert plan.is_complete
        assert plan.progress_percent == 0


class TestSelectPattern:
    def test_single_dept_with_judgment(self):
        assert select_pattern(1, True, False) == PatternType.SOLO_SPRINT

    def test_single_dept_no_judgment(self):
        assert select_pattern(1, False, False) == PatternType.SKILL_CHAIN

    def test_multi_dept_sequential(self):
        assert select_pattern(3, True, True) == PatternType.MULTI_AGENT_HANDOFF

    def test_multi_dept_default(self):
        assert select_pattern(2, False, False) == PatternType.MULTI_AGENT_HANDOFF
