"""Forge schema — Pydantic models and enums for the ArkaOS Intelligent Planning Engine.

The Forge analyses incoming requests, scores complexity across five dimensions,
selects the appropriate execution tier (shallow / standard / deep), and emits a
structured ForgePlan that downstream agents consume.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ForgeTier(str, Enum):
    """Execution tier determined by complexity score."""
    SHALLOW = "shallow"
    STANDARD = "standard"
    DEEP = "deep"


class ForgeStatus(str, Enum):
    """Lifecycle status of a ForgePlan."""
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ExplorerLens(str, Enum):
    """The analytical perspective used when exploring a plan."""
    PRAGMATIC = "pragmatic"          # Focus on fastest viable path
    ARCHITECTURAL = "architectural"  # Focus on long-term design health
    CONTRARIAN = "contrarian"        # Challenge assumptions, surface risks


class RiskSeverity(str, Enum):
    """Severity level for identified risks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionPathType(str, Enum):
    """Type of execution artefact that fulfils a plan step."""
    SKILL = "skill"
    WORKFLOW = "workflow"
    ENTERPRISE_WORKFLOW = "enterprise_workflow"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ComplexityDimensions(BaseModel):
    """Five-axis complexity breakdown, each scored 0–100."""

    scope: int = Field(default=0, description="Breadth of change across the codebase or system.")
    dependencies: int = Field(default=0, description="Number and criticality of upstream/downstream dependencies.")
    ambiguity: int = Field(default=0, description="How unclear or under-specified the requirements are.")
    risk: int = Field(default=0, description="Potential for breakage, data loss, or security impact.")
    novelty: int = Field(default=0, description="How unlike existing patterns this work is.")

    @field_validator("scope", "dependencies", "ambiguity", "risk", "novelty", mode="before")
    @classmethod
    def clamp_to_range(cls, v: int) -> int:
        """Clamp dimension value to [0, 100]."""
        return max(0, min(100, int(v)))


class ComplexityScore(BaseModel):
    """Aggregated complexity result produced by the Complexity Scorer."""

    score: int = Field(default=0, description="Composite 0–100 score derived from all dimensions.")
    tier: ForgeTier = Field(default=ForgeTier.SHALLOW, description="Execution tier selected based on the composite score.")
    dimensions: ComplexityDimensions = Field(default_factory=ComplexityDimensions, description="Per-dimension breakdown.")
    similar_plans: List[str] = Field(
        default_factory=list,
        description="IDs of previously completed plans with similar profiles.",
    )
    reused_patterns: List[str] = Field(
        default_factory=list,
        description="Named patterns from the ArkaOS pattern library reused in this plan.",
    )


# ---------------------------------------------------------------------------
# Approach & Critic Models
# ---------------------------------------------------------------------------

class KeyDecision(BaseModel):
    """A single decision made during exploration."""
    decision: str
    rationale: str = ""


class PhaseDeliverable(BaseModel):
    """A deliverable within a plan phase."""
    name: str
    deliverables: list[str] = Field(default_factory=list)
    effort: str = "medium"


class ExplorerApproach(BaseModel):
    """Output from a single explorer agent."""
    explorer: ExplorerLens
    summary: str = ""
    key_decisions: list[KeyDecision] = Field(default_factory=list)
    phases: list[PhaseDeliverable] = Field(default_factory=list)
    estimated_total_effort: str = "medium"
    risks: list[str] = Field(default_factory=list)
    reuses_patterns: list[str] = Field(default_factory=list)


class RejectedElement(BaseModel):
    """An element rejected by the critic with reason."""
    element: str
    reason: str


class IdentifiedRisk(BaseModel):
    """A risk identified by the critic with mitigation."""
    risk: str
    mitigation: str = ""
    severity: RiskSeverity = RiskSeverity.LOW


class CriticVerdict(BaseModel):
    """Synthesis output from the Plan Critic."""
    synthesis: dict[str, list[str]] = Field(default_factory=dict)
    rejected_elements: list[RejectedElement] = Field(default_factory=list)
    risks: list[IdentifiedRisk] = Field(default_factory=list)
    confidence: float = 0.0
    estimated_phases: int = 0
    estimated_departments: list[str] = Field(default_factory=list)

    def is_valid(self) -> bool:
        """Check critic rules: must reject >= 1 and identify >= 1 risk."""
        return len(self.rejected_elements) >= 1 and len(self.risks) >= 1


# ---------------------------------------------------------------------------
# ForgePlan and Context Models
# ---------------------------------------------------------------------------

class ForgeContext(BaseModel):
    """Snapshot of repo state when forge was initiated."""
    repo: str
    branch: str
    commit_at_forge: str
    arkaos_version: str
    prompt: str
    context_refreshed: bool = False


class PlanPhase(BaseModel):
    """A single phase in the forge plan."""
    name: str
    department: str
    agents: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    context_from_forge: dict[str, list[str]] = Field(default_factory=dict)


class ExecutionPath(BaseModel):
    """How the plan will be executed after approval."""
    type: ExecutionPathType = ExecutionPathType.SKILL
    target: str = ""
    departments: list[str] = Field(default_factory=list)
    estimated_commits: int = 0


class ForgeGovernance(BaseModel):
    """Governance metadata for a forge plan."""
    constitution_check: str = "pending"
    violations: list[str] = Field(default_factory=list)
    quality_gate_required: bool = True
    branch_strategy: str = ""


class ForgePlan(BaseModel):
    """Complete forge plan — the primary artifact of The Forge."""
    id: str
    name: str
    created_at: str = ""
    forged_by: str = ""
    version: int = 1

    context: ForgeContext
    complexity: ComplexityScore = Field(default_factory=ComplexityScore)
    approaches: list[ExplorerApproach] = Field(default_factory=list)
    critic: CriticVerdict = Field(default_factory=CriticVerdict)

    plan_phases: list[PlanPhase] = Field(default_factory=list)
    goal: str = ""
    execution_path: ExecutionPath = Field(default_factory=ExecutionPath)

    governance: ForgeGovernance = Field(default_factory=ForgeGovernance)

    status: ForgeStatus = ForgeStatus.DRAFT
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    executed_at: Optional[str] = None
    completion_notes: Optional[str] = None
