"""Orchestration protocol schemas.

Defines the structure for multi-agent coordination across departments.
Four patterns: Solo Sprint, Domain Deep-Dive, Multi-Agent Handoff, Skill Chain.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    SOLO_SPRINT = "solo_sprint"
    DOMAIN_DEEP_DIVE = "domain_deep_dive"
    MULTI_AGENT_HANDOFF = "multi_agent_handoff"
    SKILL_CHAIN = "skill_chain"


class PhaseHandoff(BaseModel):
    """Context passed between orchestration phases."""
    phase_number: int
    phase_name: str
    decisions: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_department: str = ""
    next_agent: str = ""
    next_skills: list[str] = Field(default_factory=list)

    def to_context(self) -> str:
        """Render handoff as context string for next phase."""
        lines = [f"Phase {self.phase_number} ({self.phase_name}) complete."]
        if self.decisions:
            lines.append(f"Decisions: {', '.join(self.decisions)}")
        if self.artifacts:
            lines.append(f"Artifacts: {', '.join(self.artifacts)}")
        if self.open_questions:
            lines.append(f"Open questions: {', '.join(self.open_questions)}")
        if self.next_department:
            lines.append(f"Next: {self.next_department}/{self.next_agent}")
        return "\n".join(lines)


class OrchestrationPhase(BaseModel):
    """A single phase in an orchestration plan."""
    number: int
    name: str
    department: str
    agent_id: str
    skills: list[str] = Field(default_factory=list)
    objective: str = ""
    outputs: list[str] = Field(default_factory=list)
    gate: str = "user_approval"  # user_approval, auto, quality_gate


class OrchestrationPlan(BaseModel):
    """A complete orchestration plan spanning multiple departments."""
    objective: str
    pattern: PatternType
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    phases: list[OrchestrationPhase] = Field(default_factory=list)
    current_phase: int = 0

    def next_phase(self) -> Optional[OrchestrationPhase]:
        """Get the next phase to execute."""
        if self.current_phase < len(self.phases):
            return self.phases[self.current_phase]
        return None

    def advance(self, handoff: PhaseHandoff) -> Optional[OrchestrationPhase]:
        """Record handoff and advance to next phase."""
        self.current_phase += 1
        return self.next_phase()

    @property
    def is_complete(self) -> bool:
        return self.current_phase >= len(self.phases)

    @property
    def progress_percent(self) -> int:
        if not self.phases:
            return 0
        return int((self.current_phase / len(self.phases)) * 100)


class OrchestrationPattern(BaseModel):
    """Definition of a coordination pattern."""
    type: PatternType
    name: str
    description: str
    when_to_use: list[str] = Field(default_factory=list)
    structure: str = ""
    example: str = ""
    anti_patterns: list[str] = Field(default_factory=list)
