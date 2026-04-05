"""Budget schema — token allocation, usage tracking, and summaries."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TierBudget(BaseModel):
    """Token budget for a single agent tier."""
    tier: int
    monthly_tokens: int          # 0 = unlimited
    per_task_max: int            # 0 = unlimited
    approval_threshold: float = 0.8  # Needs Tier 0 approval at this % used

    @property
    def is_unlimited(self) -> bool:
        return self.monthly_tokens == 0


# Default tier budgets (configurable via BudgetConfig)
DEFAULT_TIER_BUDGETS = {
    0: TierBudget(tier=0, monthly_tokens=0, per_task_max=0),           # Unlimited
    1: TierBudget(tier=1, monthly_tokens=5_000_000, per_task_max=500_000),
    2: TierBudget(tier=2, monthly_tokens=2_000_000, per_task_max=200_000),
    3: TierBudget(tier=3, monthly_tokens=1_000_000, per_task_max=100_000),
}


class BudgetConfig(BaseModel):
    """Budget configuration for the system."""
    tier_budgets: dict[int, TierBudget] = Field(default_factory=lambda: dict(DEFAULT_TIER_BUDGETS))
    billing_start_day: int = 1  # Day of month billing resets

    def get_tier_budget(self, tier: int) -> TierBudget:
        return self.tier_budgets.get(tier, DEFAULT_TIER_BUDGETS.get(tier, TierBudget(tier=tier, monthly_tokens=1_000_000, per_task_max=100_000)))


class BudgetUsage(BaseModel):
    """A single token usage record."""
    id: str
    agent_id: str
    department: str = ""
    tier: int = 2
    tokens: int = 0
    workflow_id: str = ""
    task_id: str = ""
    description: str = ""
    timestamp: str = ""
    approved_by: str = ""  # Tier 0 agent who approved overrun

    @property
    def is_overrun_approved(self) -> bool:
        return bool(self.approved_by)


class BudgetSummary(BaseModel):
    """Current budget status for a tier or department."""
    tier: int
    department: str = ""
    period_start: str = ""
    period_end: str = ""
    allocated: int = 0          # Monthly allocation
    used: int = 0               # Tokens used this period
    remaining: int = 0          # Tokens remaining
    percent_used: float = 0.0   # 0-100
    is_unlimited: bool = False
    needs_approval: bool = False  # >80% threshold
    usage_count: int = 0        # Number of operations this period
    overruns: int = 0           # Number of approved overruns

    @property
    def status(self) -> str:
        if self.is_unlimited:
            return "UNLIMITED"
        if self.percent_used >= 100:
            return "EXCEEDED"
        if self.needs_approval:
            return "APPROVAL_REQUIRED"
        if self.percent_used >= 50:
            return "MODERATE"
        return "HEALTHY"
