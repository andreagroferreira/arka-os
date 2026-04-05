"""Tests for token budget system."""

import json
import tempfile
from pathlib import Path

import pytest

from core.budget.schema import BudgetConfig, BudgetSummary, BudgetUsage, TierBudget
from core.budget.manager import BudgetManager


@pytest.fixture
def manager():
    return BudgetManager()


@pytest.fixture
def persistent_manager(tmp_path):
    return BudgetManager(storage_path=tmp_path / "budget.json")


class TestTierBudget:
    def test_tier_0_unlimited(self):
        t = TierBudget(tier=0, monthly_tokens=0, per_task_max=0)
        assert t.is_unlimited

    def test_tier_1_limited(self):
        t = TierBudget(tier=1, monthly_tokens=5_000_000, per_task_max=500_000)
        assert not t.is_unlimited
        assert t.monthly_tokens == 5_000_000


class TestBudgetConfig:
    def test_default_tiers(self):
        config = BudgetConfig()
        assert config.get_tier_budget(0).is_unlimited
        assert config.get_tier_budget(1).monthly_tokens == 5_000_000
        assert config.get_tier_budget(2).monthly_tokens == 2_000_000
        assert config.get_tier_budget(3).monthly_tokens == 1_000_000

    def test_custom_tier(self):
        config = BudgetConfig(tier_budgets={
            0: TierBudget(tier=0, monthly_tokens=0, per_task_max=0),
            1: TierBudget(tier=1, monthly_tokens=10_000_000, per_task_max=1_000_000),
        })
        assert config.get_tier_budget(1).monthly_tokens == 10_000_000


class TestBudgetManager:
    def test_record_usage(self, manager):
        usage = manager.record_usage("agent-1", tokens=10_000, tier=2, department="dev")
        assert usage.id == "usage-000001"
        assert usage.tokens == 10_000
        assert usage.agent_id == "agent-1"

    def test_period_usage_tracking(self, manager):
        manager.record_usage("agent-1", tokens=10_000, tier=2, department="dev")
        manager.record_usage("agent-2", tokens=20_000, tier=2, department="dev")
        assert manager.get_period_usage(tier=2, department="dev") == 30_000

    def test_period_usage_filters_by_tier(self, manager):
        manager.record_usage("agent-1", tokens=10_000, tier=1)
        manager.record_usage("agent-2", tokens=20_000, tier=2)
        assert manager.get_period_usage(tier=1) == 10_000
        assert manager.get_period_usage(tier=2) == 20_000

    def test_remaining_tokens(self, manager):
        manager.record_usage("agent-1", tokens=500_000, tier=2)
        remaining = manager.get_remaining(tier=2)
        assert remaining == 1_500_000  # 2M - 500K

    def test_remaining_unlimited(self, manager):
        assert manager.get_remaining(tier=0) == -1

    def test_check_budget_ok(self, manager):
        assert manager.check_budget(tier=2, estimated_tokens=100_000)

    def test_check_budget_exceeded(self, manager):
        manager.record_usage("agent-1", tokens=1_900_000, tier=2)
        assert not manager.check_budget(tier=2, estimated_tokens=200_000)

    def test_check_budget_per_task_limit(self, manager):
        # Tier 2 has 200K per-task max
        assert not manager.check_budget(tier=2, estimated_tokens=300_000)

    def test_check_budget_unlimited(self, manager):
        assert manager.check_budget(tier=0, estimated_tokens=999_999_999)

    def test_needs_approval_threshold(self, manager):
        assert not manager.needs_approval(tier=2)
        # Use 80% of 2M = 1.6M
        manager.record_usage("agent-1", tokens=1_600_000, tier=2)
        assert manager.needs_approval(tier=2)

    def test_needs_approval_unlimited(self, manager):
        assert not manager.needs_approval(tier=0)


class TestBudgetSummary:
    def test_summary_healthy(self, manager):
        manager.record_usage("agent-1", tokens=100_000, tier=2, department="dev")
        summary = manager.get_summary(tier=2, department="dev")
        assert summary.allocated == 2_000_000
        assert summary.used == 100_000
        assert summary.remaining == 1_900_000
        assert summary.percent_used == 5.0
        assert summary.status == "HEALTHY"

    def test_summary_moderate(self, manager):
        manager.record_usage("agent-1", tokens=1_200_000, tier=2)
        summary = manager.get_summary(tier=2)
        assert summary.status == "MODERATE"

    def test_summary_approval_required(self, manager):
        manager.record_usage("agent-1", tokens=1_700_000, tier=2)
        summary = manager.get_summary(tier=2)
        assert summary.needs_approval
        assert summary.status == "APPROVAL_REQUIRED"

    def test_summary_exceeded(self, manager):
        manager.record_usage("agent-1", tokens=2_100_000, tier=2)
        summary = manager.get_summary(tier=2)
        assert summary.status == "EXCEEDED"

    def test_summary_unlimited(self, manager):
        summary = manager.get_summary(tier=0)
        assert summary.is_unlimited
        assert summary.status == "UNLIMITED"

    def test_summary_usage_count(self, manager):
        manager.record_usage("a1", tokens=10_000, tier=2)
        manager.record_usage("a2", tokens=20_000, tier=2)
        manager.record_usage("a3", tokens=30_000, tier=2)
        summary = manager.get_summary(tier=2)
        assert summary.usage_count == 3


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "budget.json"
        m1 = BudgetManager(storage_path=path)
        m1.record_usage("agent-1", tokens=50_000, tier=2, department="dev")
        m1.record_usage("agent-2", tokens=30_000, tier=1, department="mkt")

        m2 = BudgetManager(storage_path=path)
        assert m2.get_period_usage(tier=2, department="dev") == 50_000
        assert m2.get_period_usage(tier=1, department="mkt") == 30_000

    def test_persistence_file_created(self, tmp_path):
        path = tmp_path / "budget.json"
        m = BudgetManager(storage_path=path)
        m.record_usage("agent-1", tokens=10_000, tier=2)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["counter"] == 1
        assert len(data["usages"]) == 1


class TestOverrunApproval:
    def test_overrun_with_approval(self, manager):
        manager.record_usage("agent-1", tokens=2_000_000, tier=2)
        # Record overrun approved by CFO
        usage = manager.record_usage(
            "agent-1", tokens=500_000, tier=2,
            approved_by="cfo-helena",
            description="Budget overrun approved for critical fix",
        )
        assert usage.is_overrun_approved
        summary = manager.get_summary(tier=2)
        assert summary.overruns == 1
