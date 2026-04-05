"""Tests that all agent YAML files load and validate correctly."""

import pytest
from pathlib import Path

from core.agents.loader import load_agent
from core.agents.validator import validate_agent_consistency
from core.agents.schema import DISCType


DEPARTMENTS_DIR = Path(__file__).parent.parent.parent / "departments"

# Collect all agent YAML files
AGENT_FILES = sorted(DEPARTMENTS_DIR.glob("*/agents/*.yaml"))


class TestAllAgentsLoad:
    """Verify every agent YAML file loads without errors."""

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.stem)
    def test_agent_loads(self, agent_file):
        agent = load_agent(agent_file)
        assert agent.id
        assert agent.name
        assert agent.role
        assert agent.department
        assert 0 <= agent.tier <= 3

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.stem)
    def test_agent_has_complete_dna(self, agent_file):
        agent = load_agent(agent_file)
        dna = agent.behavioral_dna
        # All 4 frameworks present
        assert dna.disc.primary != dna.disc.secondary
        assert dna.enneagram.type is not None
        assert 0 <= dna.big_five.openness <= 100
        assert dna.mbti.type is not None

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.stem)
    def test_agent_consistency(self, agent_file):
        agent = load_agent(agent_file)
        result = validate_agent_consistency(agent)
        # All agents should be valid (no errors, warnings are OK)
        assert result.is_valid, f"{agent.id}: {result.errors}"

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.stem)
    def test_agent_has_expertise(self, agent_file):
        agent = load_agent(agent_file)
        assert len(agent.expertise.domains) > 0
        assert len(agent.expertise.frameworks) > 0


class TestAgentHierarchy:
    """Verify the agent tier hierarchy is correct."""

    def test_tier0_agents_have_veto(self):
        tier0 = []
        for f in AGENT_FILES:
            agent = load_agent(f)
            if agent.tier == 0:
                tier0.append(agent)
        assert len(tier0) >= 4  # CTO, CFO, COO, CQO at minimum
        for agent in tier0:
            assert agent.authority.veto, f"{agent.id} is Tier 0 but has no veto"

    def test_tier1_agents_have_authority(self):
        """Tier 1 agents must have orchestrate OR approve_architecture (or both)."""
        tier1 = []
        for f in AGENT_FILES:
            agent = load_agent(f)
            if agent.tier == 1:
                tier1.append(agent)
        for agent in tier1:
            has_authority = agent.authority.orchestrate or agent.authority.approve_architecture
            assert has_authority, f"{agent.id} is Tier 1 but has no leadership authority"

    def test_total_agents_count(self):
        assert len(AGENT_FILES) >= 16, f"Expected 16+ agents, found {len(AGENT_FILES)}"

    def test_unique_agent_ids(self):
        ids = set()
        for f in AGENT_FILES:
            agent = load_agent(f)
            assert agent.id not in ids, f"Duplicate agent ID: {agent.id}"
            ids.add(agent.id)

    def test_departments_covered(self):
        departments = set()
        for f in AGENT_FILES:
            agent = load_agent(f)
            departments.add(agent.department)
        # Should have agents in most departments
        assert len(departments) >= 10, f"Only {len(departments)} departments have agents"
