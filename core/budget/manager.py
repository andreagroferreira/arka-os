"""Budget manager — track, enforce, and report on token budgets."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from core.budget.schema import BudgetConfig, BudgetSummary, BudgetUsage, TierBudget


class BudgetManager:
    """Manages token budget allocation, tracking, and enforcement.

    Budgets are tier-based with monthly reset. Usage is persisted to JSON.
    Tier 0 agents have unlimited budgets. Other tiers need Tier 0 approval
    when usage exceeds the approval threshold (default 80%).
    """

    def __init__(self, storage_path: str | Path = "", config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()
        self._usages: list[BudgetUsage] = []
        self._counter: int = 0
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path and self._storage_path.exists():
            self._load()

    def record_usage(
        self,
        agent_id: str,
        tokens: int,
        tier: int = 2,
        department: str = "",
        workflow_id: str = "",
        task_id: str = "",
        description: str = "",
        approved_by: str = "",
    ) -> BudgetUsage:
        """Record a token usage event."""
        self._counter += 1
        usage = BudgetUsage(
            id=f"usage-{self._counter:06d}",
            agent_id=agent_id,
            department=department,
            tier=tier,
            tokens=tokens,
            workflow_id=workflow_id,
            task_id=task_id,
            description=description,
            timestamp=datetime.now().isoformat(),
            approved_by=approved_by,
        )
        self._usages.append(usage)
        self._save()
        return usage

    def get_period_usage(self, tier: int, department: str = "") -> int:
        """Get total tokens used this billing period for a tier/department."""
        period_start = self._current_period_start()
        total = 0
        for u in self._usages:
            if u.tier != tier:
                continue
            if department and u.department != department:
                continue
            if u.timestamp and u.timestamp >= period_start.isoformat():
                total += u.tokens
        return total

    def get_remaining(self, tier: int, department: str = "") -> int:
        """Get remaining tokens for this period. Returns -1 for unlimited."""
        budget = self._config.get_tier_budget(tier)
        if budget.is_unlimited:
            return -1
        used = self.get_period_usage(tier, department)
        return max(0, budget.monthly_tokens - used)

    def check_budget(self, tier: int, estimated_tokens: int, department: str = "") -> bool:
        """Check if there's enough budget for an operation. True = OK."""
        budget = self._config.get_tier_budget(tier)
        if budget.is_unlimited:
            return True

        # Check per-task limit
        if budget.per_task_max > 0 and estimated_tokens > budget.per_task_max:
            return False

        # Check remaining monthly budget
        remaining = self.get_remaining(tier, department)
        return estimated_tokens <= remaining

    def needs_approval(self, tier: int, department: str = "") -> bool:
        """Check if usage has exceeded the approval threshold."""
        budget = self._config.get_tier_budget(tier)
        if budget.is_unlimited:
            return False
        used = self.get_period_usage(tier, department)
        return used >= (budget.monthly_tokens * budget.approval_threshold)

    def get_summary(self, tier: int, department: str = "") -> BudgetSummary:
        """Get a complete budget summary for a tier/department."""
        budget = self._config.get_tier_budget(tier)
        used = self.get_period_usage(tier, department)
        period_start = self._current_period_start()

        if budget.is_unlimited:
            return BudgetSummary(
                tier=tier,
                department=department,
                period_start=period_start.isoformat(),
                allocated=0,
                used=used,
                remaining=-1,
                percent_used=0,
                is_unlimited=True,
                usage_count=self._count_period_usages(tier, department),
            )

        remaining = max(0, budget.monthly_tokens - used)
        percent = (used / budget.monthly_tokens * 100) if budget.monthly_tokens > 0 else 0
        overruns = sum(
            1 for u in self._usages
            if u.tier == tier
            and (not department or u.department == department)
            and u.timestamp >= period_start.isoformat()
            and u.is_overrun_approved
        )

        return BudgetSummary(
            tier=tier,
            department=department,
            period_start=period_start.isoformat(),
            allocated=budget.monthly_tokens,
            used=used,
            remaining=remaining,
            percent_used=round(percent, 1),
            is_unlimited=False,
            needs_approval=self.needs_approval(tier, department),
            usage_count=self._count_period_usages(tier, department),
            overruns=overruns,
        )

    def reset_monthly(self) -> int:
        """Archive old usages and start a new billing period. Returns archived count."""
        period_start = self._current_period_start()
        old = [u for u in self._usages if u.timestamp < period_start.isoformat()]
        self._usages = [u for u in self._usages if u.timestamp >= period_start.isoformat()]
        self._save()
        return len(old)

    def _current_period_start(self) -> date:
        """Get the start of the current billing period."""
        today = date.today()
        day = self._config.billing_start_day
        if today.day >= day:
            return date(today.year, today.month, day)
        # Previous month
        month = today.month - 1
        year = today.year
        if month < 1:
            month = 12
            year -= 1
        return date(year, month, day)

    def _count_period_usages(self, tier: int, department: str = "") -> int:
        period_start = self._current_period_start()
        return sum(
            1 for u in self._usages
            if u.tier == tier
            and (not department or u.department == department)
            and u.timestamp >= period_start.isoformat()
        )

    def _save(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "counter": self._counter,
            "usages": [u.model_dump(mode="json") for u in self._usages],
        }
        with open(self._storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        content = self._storage_path.read_text().strip()
        if not content:
            return
        data = json.loads(content)
        self._counter = data.get("counter", 0)
        for udata in data.get("usages", []):
            self._usages.append(BudgetUsage.model_validate(udata))
