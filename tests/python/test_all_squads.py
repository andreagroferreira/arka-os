"""Tests that all squad YAML files load and validate correctly."""

import pytest
from pathlib import Path

from core.squads.loader import load_squad, load_all_squads
from core.squads.schema import SquadType


DEPARTMENTS_DIR = Path(__file__).parent.parent.parent / "departments"
SQUAD_FILES = sorted(DEPARTMENTS_DIR.glob("*/squad.yaml"))


class TestAllSquadsLoad:
    @pytest.mark.parametrize("squad_file", SQUAD_FILES, ids=lambda f: f.parent.name)
    def test_squad_loads(self, squad_file):
        squad = load_squad(squad_file)
        assert squad.id
        assert squad.name
        assert squad.department

    @pytest.mark.parametrize("squad_file", SQUAD_FILES, ids=lambda f: f.parent.name)
    def test_squad_has_lead(self, squad_file):
        squad = load_squad(squad_file)
        assert squad.has_lead, f"{squad.id} has no lead"

    @pytest.mark.parametrize("squad_file", SQUAD_FILES, ids=lambda f: f.parent.name)
    def test_squad_has_members(self, squad_file):
        squad = load_squad(squad_file)
        assert squad.size >= 1, f"{squad.id} has no members"

    @pytest.mark.parametrize("squad_file", SQUAD_FILES, ids=lambda f: f.parent.name)
    def test_squad_has_workflows(self, squad_file):
        squad = load_squad(squad_file)
        # Quality Gate is special — it's invoked by other squads
        if squad.department != "quality":
            assert len(squad.workflows) >= 1, f"{squad.id} has no workflows"

    @pytest.mark.parametrize("squad_file", SQUAD_FILES, ids=lambda f: f.parent.name)
    def test_squad_under_max_size(self, squad_file):
        squad = load_squad(squad_file)
        assert squad.size <= squad.max_size, f"{squad.id} exceeds max_size"


class TestSquadCoverage:
    def test_total_squads(self):
        squads = load_all_squads(DEPARTMENTS_DIR)
        assert len(squads) >= 16, f"Expected 16+ squads, found {len(squads)}"

    def test_all_departments_have_squads(self):
        expected_depts = {
            "dev", "marketing", "finance", "strategy", "brand",
            "ecom", "kb", "saas", "landing", "community", "content",
            "pm", "ops", "sales", "leadership", "org", "quality",
        }
        squads = load_all_squads(DEPARTMENTS_DIR)
        actual_depts = {s.department for s in squads}
        missing = expected_depts - actual_depts
        assert not missing, f"Missing squads for: {missing}"

    def test_total_agents_across_squads(self):
        squads = load_all_squads(DEPARTMENTS_DIR)
        all_agents = set()
        for squad in squads:
            for member in squad.members:
                all_agents.add(member.agent_id)
        assert len(all_agents) >= 40, f"Expected 40+ unique agents, found {len(all_agents)}"

    def test_topology_diversity(self):
        """Should have stream-aligned, platform, and enabling squads."""
        squads = load_all_squads(DEPARTMENTS_DIR)
        topologies = {s.topology.value for s in squads}
        assert "stream-aligned" in topologies
        assert "enabling" in topologies
        assert "platform" in topologies

    def test_total_workflows(self):
        squads = load_all_squads(DEPARTMENTS_DIR)
        total_workflows = sum(len(s.workflows) for s in squads)
        assert total_workflows >= 50, f"Expected 50+ workflows, found {total_workflows}"
