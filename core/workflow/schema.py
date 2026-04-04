"""Workflow schema — Pydantic models for declarative YAML workflows.

Workflows define multi-phase execution plans with:
- Sequential phases with assigned agents
- Gates between phases (user approval, quality check, auto)
- Conditions for skipping or branching
- Parallel execution of independent agents within a phase
- Quality Gate integration (mandatory for all departments)
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


class GateType(str, Enum):
    USER_APPROVAL = "user_approval"     # Requires user to confirm
    QUALITY_GATE = "quality_gate"       # Marta + Eduardo + Francisca
    AUTO = "auto"                       # Passes automatically if phase succeeds
    CONDITION = "condition"             # Passes if condition evaluates true


class Gate(BaseModel):
    """A gate between phases — controls flow progression."""
    type: GateType = GateType.AUTO
    description: str = ""
    condition: Optional[str] = None     # Python expression for CONDITION type
    required_verdict: str = "APPROVED"  # For QUALITY_GATE type
    timeout_seconds: int = 0            # 0 = no timeout


class AgentAssignment(BaseModel):
    """An agent assigned to work within a phase."""
    agent_id: str
    role: str = ""                      # What this agent does in this phase
    parallel: bool = False              # Can run in parallel with other agents
    optional: bool = False              # Phase can complete without this agent


class PhaseOutput(BaseModel):
    """Expected output from a phase."""
    type: str = "document"              # document, code, review, decision
    format: str = ""                    # markdown, yaml, json, code
    obsidian_path: str = ""             # Where to save in Obsidian vault
    description: str = ""


class Phase(BaseModel):
    """A single phase in a workflow."""
    id: str
    name: str
    description: str = ""
    agents: list[AgentAssignment] = Field(default_factory=list)
    gate: Gate = Field(default_factory=Gate)
    outputs: list[PhaseOutput] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    skip_if: Optional[str] = None       # Condition to skip this phase
    status: PhaseStatus = PhaseStatus.PENDING
    result: Optional[str] = None


class WorkflowTier(str, Enum):
    ENTERPRISE = "enterprise"           # Full 7-10 phase workflow
    FOCUSED = "focused"                 # 3-4 phases for medium tasks
    SPECIALIST = "specialist"           # 1-2 phases for simple tasks


class Workflow(BaseModel):
    """Complete workflow definition.

    A workflow is a sequence of phases with gates between them.
    Each phase has assigned agents and expected outputs.
    Quality Gate (Phase N-1) is mandatory for all workflows.
    """
    id: str
    name: str
    description: str = ""
    department: str
    tier: WorkflowTier = WorkflowTier.ENTERPRISE
    command: str = ""                   # The CLI command that triggers this

    phases: list[Phase] = Field(default_factory=list)

    # Workflow-level config
    requires_branch: bool = False       # Must run on feature branch
    requires_spec: bool = False         # Must have approved spec first
    quality_gate_required: bool = True  # Quality Gate phase mandatory
    max_duration_minutes: int = 0       # 0 = no limit

    # Runtime state
    current_phase: int = 0
    status: PhaseStatus = PhaseStatus.PENDING

    def get_current_phase(self) -> Optional[Phase]:
        """Get the currently active phase."""
        if 0 <= self.current_phase < len(self.phases):
            return self.phases[self.current_phase]
        return None

    def get_phase_by_id(self, phase_id: str) -> Optional[Phase]:
        """Find a phase by its ID."""
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        return None

    def all_phases_complete(self) -> bool:
        """Check if all phases are completed or skipped."""
        return all(
            p.status in (PhaseStatus.COMPLETED, PhaseStatus.SKIPPED)
            for p in self.phases
        )

    def next_phase(self) -> Optional[Phase]:
        """Get the next pending phase."""
        for i, phase in enumerate(self.phases):
            if phase.status == PhaseStatus.PENDING:
                self.current_phase = i
                return phase
        return None
