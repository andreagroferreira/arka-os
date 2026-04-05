"""Squad registry — manages all squads and enables cross-department collaboration."""

from typing import Optional
from core.squads.schema import Squad, SquadMember, SquadType, TeamTopologyType


class SquadRegistry:
    """Central registry for all squads.

    Manages department squads (loaded from YAML) and project squads
    (assembled dynamically). Enables the matrix structure:
    agents belong to a department squad but can be borrowed
    into project squads.
    """

    def __init__(self) -> None:
        self._squads: dict[str, Squad] = {}

    def register(self, squad: Squad) -> None:
        """Register a squad."""
        self._squads[squad.id] = squad

    def get(self, squad_id: str) -> Optional[Squad]:
        """Get a squad by ID."""
        return self._squads.get(squad_id)

    def get_by_department(self, department: str) -> Optional[Squad]:
        """Get the department squad for a given department."""
        for squad in self._squads.values():
            if squad.department == department and squad.squad_type == SquadType.DEPARTMENT:
                return squad
        return None

    def get_by_prefix(self, prefix: str) -> Optional[Squad]:
        """Get squad by CLI prefix (e.g., '/dev', '/mkt')."""
        for squad in self._squads.values():
            if squad.skills_prefix == prefix:
                return squad
        return None

    def list_all(self) -> list[Squad]:
        """List all registered squads."""
        return list(self._squads.values())

    def list_by_type(self, squad_type: SquadType) -> list[Squad]:
        """List squads of a specific type."""
        return [s for s in self._squads.values() if s.squad_type == squad_type]

    def create_project_squad(
        self,
        project_id: str,
        name: str,
        description: str,
        members: list[dict],
    ) -> Squad:
        """Assemble an ad-hoc project squad from agents across departments.

        This is the matrix structure in action: agents from different
        department squads are borrowed into a temporary project squad.

        Args:
            project_id: Unique ID for the project squad.
            name: Human-readable name.
            description: What this squad is working on.
            members: List of dicts with agent_id and optional role.

        Returns:
            The assembled project Squad.
        """
        squad_members = []
        for m in members:
            agent_id = m["agent_id"]
            role = m.get("role", "")

            # Find which department this agent belongs to
            source_dept = self._find_agent_department(agent_id)

            squad_members.append(SquadMember(
                agent_id=agent_id,
                role=role,
                is_lead=m.get("is_lead", False),
                borrowed=True,
                source_department=source_dept,
                availability=m.get("availability", 0.5),
            ))

        squad = Squad(
            id=f"project-{project_id}",
            name=name,
            description=description,
            department="cross-department",
            squad_type=SquadType.PROJECT,
            topology=TeamTopologyType.STREAM_ALIGNED,
            members=squad_members,
        )

        self.register(squad)
        return squad

    def disband_project_squad(self, squad_id: str) -> bool:
        """Disband a project squad, returning agents to their departments."""
        squad = self._squads.get(squad_id)
        if squad is None or squad.squad_type != SquadType.PROJECT:
            return False
        del self._squads[squad_id]
        return True

    def find_agent_across_squads(self, agent_id: str) -> list[Squad]:
        """Find all squads an agent belongs to."""
        return [
            s for s in self._squads.values()
            if any(m.agent_id == agent_id for m in s.members)
        ]

    def _find_agent_department(self, agent_id: str) -> str:
        """Find which department an agent belongs to."""
        for squad in self._squads.values():
            if squad.squad_type == SquadType.DEPARTMENT:
                if any(m.agent_id == agent_id for m in squad.members):
                    return squad.department
        return "unknown"

    @property
    def total_squads(self) -> int:
        return len(self._squads)

    @property
    def total_agents(self) -> int:
        """Count unique agents across all squads."""
        agents = set()
        for squad in self._squads.values():
            for member in squad.members:
                agents.add(member.agent_id)
        return len(agents)

    def summary(self) -> dict:
        """Get registry summary stats."""
        dept_squads = self.list_by_type(SquadType.DEPARTMENT)
        project_squads = self.list_by_type(SquadType.PROJECT)
        return {
            "total_squads": self.total_squads,
            "department_squads": len(dept_squads),
            "project_squads": len(project_squads),
            "total_agents": self.total_agents,
        }
