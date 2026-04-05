"""Tests for the Squad Framework."""

import pytest
from pathlib import Path

from core.squads.schema import Squad, SquadMember, SquadType, TeamTopologyType
from core.squads.registry import SquadRegistry
from core.squads.loader import load_squad


# --- Fixtures ---

def make_member(agent_id: str, is_lead: bool = False, **kwargs) -> SquadMember:
    return SquadMember(agent_id=agent_id, is_lead=is_lead, **kwargs)


def make_squad(id: str = "test-squad", members: list[SquadMember] | None = None, **kwargs) -> Squad:
    defaults = {
        "id": id,
        "name": "Test Squad",
        "department": "dev",
        "members": members or [
            make_member("lead-1", is_lead=True),
            make_member("dev-1"),
            make_member("dev-2"),
        ],
    }
    defaults.update(kwargs)
    return Squad(**defaults)


def make_registry_with_squads() -> SquadRegistry:
    reg = SquadRegistry()
    reg.register(make_squad("dev-squad", department="dev", skills_prefix="/dev", members=[
        make_member("cto-marco"),
        make_member("tech-lead-paulo", is_lead=True),
        make_member("backend-andre"),
        make_member("frontend-diana"),
    ]))
    reg.register(make_squad("mkt-squad", department="marketing", skills_prefix="/mkt", members=[
        make_member("mkt-director", is_lead=True),
        make_member("seo-specialist"),
        make_member("content-marketer"),
    ]))
    reg.register(make_squad("brand-squad", department="brand", skills_prefix="/brand", members=[
        make_member("brand-director", is_lead=True),
        make_member("visual-designer"),
    ]))
    return reg


# --- Schema Tests ---

class TestSquadSchema:
    def test_create_squad(self):
        squad = make_squad()
        assert squad.id == "test-squad"
        assert squad.size == 3
        assert squad.squad_type == SquadType.DEPARTMENT

    def test_get_lead(self):
        squad = make_squad()
        lead = squad.get_lead()
        assert lead is not None
        assert lead.agent_id == "lead-1"

    def test_no_lead_returns_none(self):
        squad = make_squad(members=[make_member("dev-1"), make_member("dev-2")])
        assert squad.get_lead() is None

    def test_get_member(self):
        squad = make_squad()
        member = squad.get_member("dev-1")
        assert member is not None
        assert member.agent_id == "dev-1"

    def test_get_member_not_found(self):
        squad = make_squad()
        assert squad.get_member("nonexistent") is None

    def test_borrowed_members(self):
        squad = make_squad(members=[
            make_member("local-1"),
            make_member("borrowed-1", borrowed=True, source_department="marketing"),
        ])
        borrowed = squad.borrowed_members()
        assert len(borrowed) == 1
        assert borrowed[0].source_department == "marketing"

    def test_has_lead(self):
        squad = make_squad()
        assert squad.has_lead is True

    def test_team_topology_types(self):
        for tt in TeamTopologyType:
            squad = make_squad(topology=tt)
            assert squad.topology == tt


# --- Registry Tests ---

class TestSquadRegistry:
    def test_register_and_get(self):
        reg = SquadRegistry()
        squad = make_squad()
        reg.register(squad)
        assert reg.get("test-squad") is not None

    def test_get_by_department(self):
        reg = make_registry_with_squads()
        squad = reg.get_by_department("dev")
        assert squad is not None
        assert squad.department == "dev"

    def test_get_by_prefix(self):
        reg = make_registry_with_squads()
        squad = reg.get_by_prefix("/mkt")
        assert squad is not None
        assert squad.department == "marketing"

    def test_list_all(self):
        reg = make_registry_with_squads()
        assert len(reg.list_all()) == 3

    def test_list_by_type(self):
        reg = make_registry_with_squads()
        dept_squads = reg.list_by_type(SquadType.DEPARTMENT)
        assert len(dept_squads) == 3

    def test_total_agents(self):
        reg = make_registry_with_squads()
        assert reg.total_agents == 9  # 4 + 3 + 2

    def test_summary(self):
        reg = make_registry_with_squads()
        s = reg.summary()
        assert s["total_squads"] == 3
        assert s["department_squads"] == 3
        assert s["project_squads"] == 0
        assert s["total_agents"] == 9


class TestProjectSquads:
    def test_create_project_squad(self):
        reg = make_registry_with_squads()
        project = reg.create_project_squad(
            project_id="launch-campaign",
            name="Launch Campaign",
            description="Cross-department launch for product X",
            members=[
                {"agent_id": "content-marketer", "role": "Content creation"},
                {"agent_id": "visual-designer", "role": "Visual assets", "is_lead": True},
                {"agent_id": "frontend-diana", "role": "Landing page"},
            ],
        )
        assert project.squad_type == SquadType.PROJECT
        assert project.size == 3
        assert project.has_lead
        assert all(m.borrowed for m in project.members)

    def test_project_squad_finds_source_dept(self):
        reg = make_registry_with_squads()
        project = reg.create_project_squad(
            project_id="test",
            name="Test",
            description="Test",
            members=[{"agent_id": "frontend-diana"}],
        )
        assert project.members[0].source_department == "dev"

    def test_disband_project_squad(self):
        reg = make_registry_with_squads()
        reg.create_project_squad(
            project_id="temp",
            name="Temp",
            description="Temp",
            members=[{"agent_id": "backend-andre"}],
        )
        assert reg.get("project-temp") is not None
        assert reg.disband_project_squad("project-temp") is True
        assert reg.get("project-temp") is None

    def test_cannot_disband_department_squad(self):
        reg = make_registry_with_squads()
        assert reg.disband_project_squad("dev-squad") is False

    def test_find_agent_across_squads(self):
        reg = make_registry_with_squads()
        reg.create_project_squad(
            project_id="multi",
            name="Multi",
            description="Test",
            members=[{"agent_id": "frontend-diana"}],
        )
        squads = reg.find_agent_across_squads("frontend-diana")
        assert len(squads) == 2  # dev-squad + project-multi

    def test_summary_with_project_squads(self):
        reg = make_registry_with_squads()
        reg.create_project_squad(
            project_id="p1", name="P1", description="P1",
            members=[{"agent_id": "backend-andre"}],
        )
        s = reg.summary()
        assert s["department_squads"] == 3
        assert s["project_squads"] == 1


# --- YAML Loader Tests ---

class TestSquadLoader:
    def test_load_dev_squad_yaml(self):
        path = Path(__file__).parent.parent.parent / "departments" / "dev" / "squad.yaml"
        if path.exists():
            squad = load_squad(path)
            assert squad.id == "dev-squad"
            assert squad.department == "dev"
            assert squad.skills_prefix == "/dev"
            assert squad.size == 9
            assert squad.has_lead
            lead = squad.get_lead()
            assert lead.agent_id == "tech-lead-paulo"
            assert len(squad.workflows) == 5

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_squad("/nonexistent/squad.yaml")
