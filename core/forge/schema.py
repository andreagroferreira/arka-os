"""Forge schema — Pydantic models and enums for the ArkaOS Intelligent Planning Engine.

The Forge analyses incoming requests, scores complexity across five dimensions,
selects the appropriate execution tier (shallow / standard / deep), and emits a
structured ForgePlan that downstream agents consume.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, validator


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

    @validator("scope", "dependencies", "ambiguity", "risk", "novelty", pre=True)
    def clamp_to_range(cls, v: int) -> int:
        """Clamp dimension value to [0, 100]."""
        return max(0, min(100, int(v)))


class ComplexityScore(BaseModel):
    """Aggregated complexity result produced by the Complexity Scorer."""

    score: int = Field(description="Composite 0–100 score derived from all dimensions.")
    tier: ForgeTier = Field(description="Execution tier selected based on the composite score.")
    dimensions: ComplexityDimensions = Field(description="Per-dimension breakdown.")
    similar_plans: List[str] = Field(
        default_factory=list,
        description="IDs of previously completed plans with similar profiles.",
    )
    reused_patterns: List[str] = Field(
        default_factory=list,
        description="Named patterns from the ArkaOS pattern library reused in this plan.",
    )
