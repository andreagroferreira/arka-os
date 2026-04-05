"""Squad schema — Pydantic models for squad definitions.

Squads come in two flavors:
- Department squads: Fixed teams within a department (e.g., Dev squad with 9 agents)
- Project squads: Ad-hoc cross-department teams assembled for a specific task

Inspired by Spotify Model (squads/tribes/chapters) and Team Topologies
(stream-aligned, platform, enabling, complicated-subsystem).
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SquadType(str, Enum):
    DEPARTMENT = "department"        # Fixed department squad
    PROJECT = "project"              # Ad-hoc cross-department squad
    PLATFORM = "platform"            # Internal platform team (Team Topologies)
    ENABLING = "enabling"            # Temporary capability boost


class TeamTopologyType(str, Enum):
    STREAM_ALIGNED = "stream-aligned"
    PLATFORM = "platform"
    ENABLING = "enabling"
    COMPLICATED_SUBSYSTEM = "complicated-subsystem"


class SquadMember(BaseModel):
    """An agent assigned to a squad."""
    agent_id: str
    role: str = ""                   # Role within this squad
    is_lead: bool = False            # Is this agent the squad lead?
    borrowed: bool = False           # Borrowed from another department?
    source_department: str = ""      # Original department if borrowed
    availability: float = 1.0        # 0.0-1.0, for shared agents
    # Tier 2 agents can collaborate directly within project squads
    # without requiring Tier 1 approval for each interaction.
    can_collaborate_directly: bool = True


class SquadWorkflow(BaseModel):
    """Reference to a workflow this squad uses."""
    workflow_id: str
    trigger_command: str = ""        # CLI command that triggers this workflow
    tier: str = "enterprise"         # enterprise, focused, specialist


class Squad(BaseModel):
    """A squad of agents working together.

    Department squads are defined in YAML and loaded at startup.
    Project squads are assembled dynamically from multiple departments.
    """
    id: str
    name: str
    description: str = ""
    department: str                  # Primary department
    squad_type: SquadType = SquadType.DEPARTMENT
    topology: TeamTopologyType = TeamTopologyType.STREAM_ALIGNED

    members: list[SquadMember] = Field(default_factory=list)
    workflows: list[SquadWorkflow] = Field(default_factory=list)

    # Squad metadata
    max_size: int = 10               # Max members (Two-Pizza Team rule)
    skills_prefix: str = ""          # CLI prefix (e.g., "/dev", "/mkt")
    obsidian_path: str = ""          # Output path in Obsidian vault
    quality_gate_required: bool = True

    def get_lead(self) -> Optional[SquadMember]:
        """Get the squad lead."""
        for member in self.members:
            if member.is_lead:
                return member
        return None

    def get_member(self, agent_id: str) -> Optional[SquadMember]:
        """Find a member by agent ID."""
        for member in self.members:
            if member.agent_id == agent_id:
                return member
        return None

    def borrowed_members(self) -> list[SquadMember]:
        """Get all members borrowed from other departments."""
        return [m for m in self.members if m.borrowed]

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def has_lead(self) -> bool:
        return self.get_lead() is not None
