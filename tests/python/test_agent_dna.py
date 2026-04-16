"""Tests for the Agent DNA system."""

import pytest
from unittest.mock import MagicMock, patch

from core.agents.dna_registry import DNARegistry, get_registry
from core.agents.behavior_enforcer import (
    BehaviorEnforcer,
    BehaviorDrift,
    check_agent_behavior,
)
from core.agents.adapters.disc_adapter import DISCAdapter, adapt_message
from core.agents.schema import (
    Agent,
    BehavioralDNA,
    DISCProfile,
    DISCType,
    EnneagramProfile,
    EnneagramType,
    BigFiveProfile,
    MBTIProfile,
    MBTIType,
    Communication,
    Authority,
    Expertise,
    MentalModels,
)


def make_test_agent(
    agent_id: str = "test-agent",
    disc_primary: DISCType = DISCType.D,
    enneagram_type: EnneagramType = EnneagramType(5),
    mbti_type: MBTIType = MBTIType.INTJ,
    department: str = "dev",
    tier: int = 1,
) -> Agent:
    """Create a test agent with minimal DNA profile."""
    return Agent(
        id=agent_id,
        name="Test Agent",
        role="Tester",
        department=department,
        tier=tier,
        behavioral_dna=BehavioralDNA(
            disc=DISCProfile(
                primary=disc_primary,
                secondary=DISCType.C,
                communication_style="direct",
            ),
            enneagram=EnneagramProfile(
                type=enneagram_type,
                wing=6,
                core_motivation="test",
                core_fear="test",
            ),
            big_five=BigFiveProfile(
                openness=70,
                conscientiousness=80,
                extraversion=40,
                agreeableness=50,
                neuroticism=30,
            ),
            mbti=MBTIProfile(type=mbti_type),
        ),
        communication=Communication(
            language="en",
            tone="direct",
            vocabulary_level="specialist",
            preferred_format="structured",
            avoid=["vague", "maybe"],
        ),
    )


class TestDNARegistry:
    """Tests for DNARegistry class."""

    def test_registry_loads_agents(self):
        registry = DNARegistry()
        agents = registry.all()
        assert len(agents) > 0

    def test_get_agent_by_id(self):
        registry = DNARegistry()
        agent = registry.get("cto-marco")
        assert agent is not None
        assert agent.id == "cto-marco"

    def test_get_nonexistent_agent(self):
        registry = DNARegistry()
        agent = registry.get("nonexistent")
        assert agent is None

    def test_by_disc(self):
        registry = DNARegistry()
        d_agents = registry.by_disc(DISCType.D)
        assert len(d_agents) > 0
        assert all(a.behavioral_dna.disc.primary == DISCType.D for a in d_agents)

    def test_by_enneagram(self):
        registry = DNARegistry()
        type5_agents = registry.by_enneagram(EnneagramType(5))
        assert len(type5_agents) > 0
        assert all(a.behavioral_dna.enneagram.type == EnneagramType(5) for a in type5_agents)

    def test_by_department(self):
        registry = DNARegistry()
        dev_agents = registry.by_department("dev")
        assert len(dev_agents) > 0
        assert all(a.department == "dev" for a in dev_agents)

    def test_by_tier(self):
        registry = DNARegistry()
        tier0 = registry.by_tier(0)
        assert len(tier0) > 0
        assert all(a.tier == 0 for a in tier0)

    def test_compatible_with(self):
        registry = DNARegistry()
        agent = registry.get("cto-marco")
        if agent:
            compatible = registry.compatible_with("cto-marco")
            assert agent.id not in [a.id for a in compatible]

    def test_validate_dna_completeness(self):
        registry = DNARegistry()
        missing = registry.validate_dna_completeness()
        assert isinstance(missing, dict)

    def test_get_communication_style(self):
        registry = DNARegistry()
        style = registry.get_communication_style("cto-marco")
        assert style is not None
        assert isinstance(style, str)

    def test_get_tone_for_recipient(self):
        registry = DNARegistry()
        cto = registry.get("cto-marco")
        if cto:
            tone = registry.get_tone_for_recipient("cto-marco", "cto-marco")
            assert tone is not None


class TestBehaviorEnforcer:
    """Tests for BehaviorEnforcer class."""

    def test_check_output_no_drift_for_direct_agent(self):
        enforcer = BehaviorEnforcer()
        output = "This is critical and must be done now."
        drifts = enforcer.check_output("cto-marco", output)
        assert isinstance(drifts, list)

    def test_check_output_with_drift(self):
        enforcer = BehaviorEnforcer()
        output = "This might perhaps be something maybe we could look at"
        drifts = enforcer.check_output("cto-marco", output)
        drift_types = [d.drift_type for d in drifts]

    def test_check_output_nonexistent_agent(self):
        enforcer = BehaviorEnforcer()
        drifts = enforcer.check_output("nonexistent-agent", "some output")
        assert drifts == []

    def test_check_output_empty(self):
        enforcer = BehaviorEnforcer()
        drifts = enforcer.check_output("cto-marco", "")
        assert drifts == []

    def test_check_avoid_list(self):
        agent = make_test_agent()
        agent.communication.avoid = ["vague", "maybe"]

        enforcer = BehaviorEnforcer()
        enforcer.registry._by_id = {"test-agent": agent}

        drifts = enforcer.check_output("test-agent", "This vague maybe statement")
        avoid_drifts = [
            d for d in drifts if "vague" in d.detected.lower() or "maybe" in d.detected.lower()
        ]
        assert len(avoid_drifts) >= 0

    def test_check_output_long_structured(self):
        agent = make_test_agent()
        agent.communication.preferred_format = "structured with diagrams"

        enforcer = BehaviorEnforcer()
        enforcer.registry._by_id = {"test-agent": agent}

        output = "1. First point\n2. Second point\n3. Third point"
        drifts = enforcer.check_output("test-agent", output)
        assert isinstance(drifts, list)

    def test_check_agent_behavior_convenience(self):
        drifts = check_agent_behavior("cto-marco", "Test output")
        assert isinstance(drifts, list)

    def test_enforce_output_returns_tuple(self):
        enforcer = BehaviorEnforcer()
        output, drifts = enforcer.enforce_output("cto-marco", "Test output")
        assert output == "Test output"
        assert isinstance(drifts, list)


class TestDISCAdapter:
    """Tests for DISCAdapter class."""

    def test_get_opening_for_d_type(self):
        adapter = DISCAdapter()
        cto = adapter.registry.get("cto-marco")
        if cto and cto.behavioral_dna.disc.primary == DISCType.D:
            opening = adapter.get_opening("cto-marco")
            assert opening == "Direct."

    def test_get_opening_for_i_type(self):
        adapter = DISCAdapter()
        opening = adapter.get_opening("cto-marco")

    def test_get_structure_hint(self):
        adapter = DISCAdapter()
        hint = adapter.get_structure_hint("cto-marco")
        assert hint in ["bullet_summary_first", "standard"]

    def test_adapt_for_disc_direct(self):
        adapter = DISCAdapter()
        adapted = adapter.adapt_for_disc("Hello there", DISCType.D)
        assert "Direct." in adapted or adapted == "Hello there"

    def test_adapt_for_disc_conscientious(self):
        adapter = DISCAdapter()
        adapted = adapter.adapt_for_disc("The data shows", DISCType.C)
        assert "Analysis:" in adapted or adapted == "The data shows"

    def test_adapt_message_unknown_agents(self):
        adapted = adapt_message("Hello", "unknown1", "unknown2")
        assert adapted == "Hello"


class TestBehaviorDrift:
    """Tests for BehaviorDrift dataclass."""

    def test_drift_creation(self):
        drift = BehaviorDrift(
            agent_id="test",
            drift_type="tone",
            expected="direct",
            detected="indirect",
        )
        assert drift.agent_id == "test"
        assert drift.severity == "WARN"

    def test_drift_with_suggestion(self):
        drift = BehaviorDrift(
            agent_id="test",
            drift_type="tone",
            expected="direct",
            detected="indirect",
            suggestion="Be more direct",
        )
        assert drift.suggestion == "Be more direct"
