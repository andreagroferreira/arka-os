"""Tests for the agent schema, loader, and validator."""

import pytest
import yaml
from pathlib import Path

from core.agents.schema import (
    Agent, BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType, BigFiveProfile,
    MBTIProfile, MBTIType, CognitiveFunction,
    Authority, MentalModels, MBTI_STACKS,
    ENNEAGRAM_GROWTH, ENNEAGRAM_STRESS,
)
from core.agents.validator import validate_agent_consistency, ValidationResult
from core.agents.loader import load_agent, agent_to_yaml


# --- Fixtures ---

def make_dna(**overrides) -> BehavioralDNA:
    """Create a valid BehavioralDNA with optional overrides."""
    defaults = {
        "disc": DISCProfile(primary=DISCType.D, secondary=DISCType.C),
        "enneagram": EnneagramProfile(type=EnneagramType.CHALLENGER, wing=7),
        "big_five": BigFiveProfile(
            openness=70, conscientiousness=80,
            extraversion=60, agreeableness=40, neuroticism=25
        ),
        "mbti": MBTIProfile(type=MBTIType.ENTJ),
    }
    defaults.update(overrides)
    return BehavioralDNA(**defaults)


def make_agent(**overrides) -> Agent:
    """Create a valid Agent with optional overrides."""
    defaults = {
        "id": "test-agent",
        "name": "Test",
        "role": "Test Agent",
        "department": "dev",
        "tier": 1,
        "behavioral_dna": make_dna(),
    }
    defaults.update(overrides)
    return Agent(**defaults)


# --- DISC Tests ---

class TestDISC:
    def test_valid_disc_profile(self):
        disc = DISCProfile(primary=DISCType.D, secondary=DISCType.C)
        assert disc.primary == DISCType.D
        assert disc.secondary == DISCType.C
        assert disc.label == "Driver-Analyst"

    def test_auto_label_generation(self):
        disc = DISCProfile(primary=DISCType.I, secondary=DISCType.S)
        assert disc.label == "Inspirer-Supporter"

    def test_custom_label_preserved(self):
        disc = DISCProfile(primary=DISCType.D, secondary=DISCType.C, label="Custom Label")
        assert disc.label == "Custom Label"

    def test_same_primary_secondary_rejected(self):
        with pytest.raises(ValueError, match="primary and secondary must be different"):
            DISCProfile(primary=DISCType.D, secondary=DISCType.D)

    def test_all_combinations_valid(self):
        types = list(DISCType)
        for p in types:
            for s in types:
                if p != s:
                    disc = DISCProfile(primary=p, secondary=s)
                    assert disc.label


# --- Enneagram Tests ---

class TestEnneagram:
    def test_valid_enneagram(self):
        e = EnneagramProfile(type=EnneagramType.INVESTIGATOR, wing=6)
        assert e.type == EnneagramType.INVESTIGATOR
        assert e.wing == 6
        assert e.label == "5w6 — The Investigator"

    def test_auto_fills_arrows(self):
        e = EnneagramProfile(type=EnneagramType.INVESTIGATOR, wing=6)
        assert e.growth_arrow == ENNEAGRAM_GROWTH[5]  # 8
        assert e.stress_arrow == ENNEAGRAM_STRESS[5]  # 7

    def test_invalid_wing_rejected(self):
        with pytest.raises(ValueError):
            # Type 5 can only have wing 4 or 6
            EnneagramProfile(type=EnneagramType.INVESTIGATOR, wing=3)

    def test_all_types_have_valid_wings(self):
        for t in EnneagramType:
            v = t.value
            valid_wings = {v - 1 if v > 1 else 9, v + 1 if v < 9 else 1}
            for w in valid_wings:
                e = EnneagramProfile(type=t, wing=w)
                assert e.wing == w


# --- Big Five Tests ---

class TestBigFive:
    def test_valid_big_five(self):
        bf = BigFiveProfile(openness=70, conscientiousness=80, extraversion=50, agreeableness=40, neuroticism=30)
        assert bf.openness == 70

    def test_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            BigFiveProfile(openness=101, conscientiousness=80, extraversion=50, agreeableness=40, neuroticism=30)

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            BigFiveProfile(openness=-1, conscientiousness=80, extraversion=50, agreeableness=40, neuroticism=30)


# --- MBTI Tests ---

class TestMBTI:
    def test_auto_fills_cognitive_stack(self):
        m = MBTIProfile(type=MBTIType.INTJ)
        assert m.dominant == CognitiveFunction.Ni
        assert m.auxiliary == CognitiveFunction.Te
        assert m.tertiary == CognitiveFunction.Fi
        assert m.inferior == CognitiveFunction.Se

    def test_all_types_have_stacks(self):
        for mbti_type in MBTIType:
            m = MBTIProfile(type=mbti_type)
            stack = MBTI_STACKS[mbti_type.value]
            assert m.dominant.value == stack[0]
            assert m.auxiliary.value == stack[1]


# --- Complete Agent Tests ---

class TestAgent:
    def test_create_valid_agent(self):
        agent = make_agent()
        assert agent.id == "test-agent"
        assert agent.name == "Test"
        assert agent.tier == 1

    def test_auto_memory_path(self):
        agent = make_agent(id="cto-marco")
        assert "arka-cto-marco" in agent.memory_path

    def test_tier_range_enforced(self):
        with pytest.raises(ValueError):
            make_agent(tier=5)

    def test_full_agent_from_dict(self):
        data = {
            "id": "cto-marco",
            "name": "Marco",
            "role": "CTO",
            "department": "dev",
            "tier": 0,
            "behavioral_dna": {
                "disc": {"primary": "D", "secondary": "C"},
                "enneagram": {"type": 5, "wing": 6},
                "big_five": {"openness": 78, "conscientiousness": 85, "extraversion": 35, "agreeableness": 40, "neuroticism": 25},
                "mbti": {"type": "INTJ"},
            },
            "authority": {"veto": True, "approve_architecture": True},
        }
        agent = Agent.model_validate(data)
        assert agent.name == "Marco"
        assert agent.behavioral_dna.disc.label == "Driver-Analyst"
        assert agent.behavioral_dna.enneagram.label == "5w6 — The Investigator"
        assert agent.behavioral_dna.mbti.dominant == CognitiveFunction.Ni


# --- Model Routing Tests ---

class TestModelRouting:
    def test_model_haiku(self):
        agent = make_agent(model="haiku")
        assert agent.model == "haiku"
        assert agent.get_model() == "haiku"

    def test_model_sonnet(self):
        agent = make_agent(model="sonnet")
        assert agent.get_model() == "sonnet"

    def test_model_opus(self):
        agent = make_agent(model="opus")
        assert agent.get_model() == "opus"

    def test_model_none_derives_from_tier_zero(self):
        agent = make_agent(tier=0)
        assert agent.model is None
        assert agent.get_model() == "opus"

    def test_model_none_derives_from_tier_one(self):
        agent = make_agent(tier=1)
        assert agent.get_model() == "sonnet"

    def test_model_none_derives_from_tier_two(self):
        agent = make_agent(tier=2)
        assert agent.get_model() == "sonnet"

    def test_invalid_model_rejected(self):
        with pytest.raises(ValueError):
            make_agent(model="gpt-4")


# --- Validator Tests ---

class TestValidator:
    def test_consistent_dc_agent(self):
        """D+C with Enneagram 8, INTJ, high C low A — fully consistent."""
        agent = make_agent(
            tier=0,
            behavioral_dna=make_dna(
                disc=DISCProfile(primary=DISCType.D, secondary=DISCType.C),
                enneagram=EnneagramProfile(type=EnneagramType.CHALLENGER, wing=7),
                big_five=BigFiveProfile(openness=70, conscientiousness=85, extraversion=60, agreeableness=35, neuroticism=20),
                mbti=MBTIProfile(type=MBTIType.ENTJ),
            ),
            authority=Authority(veto=True),
        )
        result = validate_agent_consistency(agent)
        assert result.is_valid
        assert result.score >= 0.7
        assert len(result.errors) == 0

    def test_inconsistent_profile_warns(self):
        """S primary with Enneagram 8 (challenger) — unusual combination."""
        agent = make_agent(
            behavioral_dna=make_dna(
                disc=DISCProfile(primary=DISCType.S, secondary=DISCType.I),
                enneagram=EnneagramProfile(type=EnneagramType.CHALLENGER, wing=7),
                mbti=MBTIProfile(type=MBTIType.ENTJ),
            ),
        )
        result = validate_agent_consistency(agent)
        assert result.is_valid  # warnings, not errors
        assert len(result.warnings) > 0

    def test_tier2_with_veto_is_error(self):
        """Tier 2 agents should not have veto power."""
        agent = make_agent(
            tier=2,
            authority=Authority(veto=True),
        )
        result = validate_agent_consistency(agent)
        assert not result.is_valid
        assert any("veto" in e.lower() for e in result.errors)


# --- YAML Loader Tests ---

class TestLoader:
    def test_load_cto_yaml(self):
        cto_path = Path(__file__).parent.parent.parent / "departments" / "dev" / "agents" / "cto.yaml"
        if cto_path.exists():
            agent = load_agent(cto_path)
            assert agent.id == "cto-marco"
            assert agent.name == "Marco"
            assert agent.tier == 0
            assert agent.behavioral_dna.disc.primary == DISCType.D
            assert agent.authority.veto is True

    def test_roundtrip_yaml(self):
        agent = make_agent()
        yaml_str = agent_to_yaml(agent)
        data = yaml.safe_load(yaml_str)
        reloaded = Agent.model_validate(data)
        assert reloaded.id == agent.id
        assert reloaded.behavioral_dna.disc.primary == agent.behavioral_dna.disc.primary
