"""Tests for The Forge — schema enums and base complexity models."""

import pytest

from core.forge.schema import (
    ForgeTier,
    ForgeStatus,
    ExplorerLens,
    RiskSeverity,
    ExecutionPathType,
    ComplexityDimensions,
    ComplexityScore,
)


# --- ForgeTier ---

class TestForgeTier:
    def test_values_exist(self) -> None:
        assert ForgeTier.SHALLOW == "shallow"
        assert ForgeTier.STANDARD == "standard"
        assert ForgeTier.DEEP == "deep"

    def test_is_string_enum(self) -> None:
        assert isinstance(ForgeTier.SHALLOW, str)

    def test_all_three_tiers(self) -> None:
        tiers = [t.value for t in ForgeTier]
        assert set(tiers) == {"shallow", "standard", "deep"}


# --- ForgeStatus ---

class TestForgeStatus:
    def test_all_lifecycle_values_exist(self) -> None:
        values = {s.value for s in ForgeStatus}
        assert "draft" in values
        assert "reviewing" in values
        assert "approved" in values
        assert "executing" in values
        assert "completed" in values
        assert "rejected" in values
        assert "cancelled" in values
        assert "archived" in values

    def test_is_string_enum(self) -> None:
        assert isinstance(ForgeStatus.DRAFT, str)

    def test_count(self) -> None:
        assert len(ForgeStatus) == 8


# --- ExplorerLens ---

class TestExplorerLens:
    def test_values_exist(self) -> None:
        assert ExplorerLens.PRAGMATIC == "pragmatic"
        assert ExplorerLens.ARCHITECTURAL == "architectural"
        assert ExplorerLens.CONTRARIAN == "contrarian"

    def test_is_string_enum(self) -> None:
        assert isinstance(ExplorerLens.PRAGMATIC, str)

    def test_all_three_lenses(self) -> None:
        lenses = [l.value for l in ExplorerLens]
        assert set(lenses) == {"pragmatic", "architectural", "contrarian"}


# --- RiskSeverity ---

class TestRiskSeverity:
    def test_values_exist(self) -> None:
        assert RiskSeverity.LOW == "low"
        assert RiskSeverity.MEDIUM == "medium"
        assert RiskSeverity.HIGH == "high"

    def test_is_string_enum(self) -> None:
        assert isinstance(RiskSeverity.LOW, str)


# --- ExecutionPathType ---

class TestExecutionPathType:
    def test_values_exist(self) -> None:
        assert ExecutionPathType.SKILL == "skill"
        assert ExecutionPathType.WORKFLOW == "workflow"
        assert ExecutionPathType.ENTERPRISE_WORKFLOW == "enterprise_workflow"

    def test_is_string_enum(self) -> None:
        assert isinstance(ExecutionPathType.SKILL, str)


# --- ComplexityDimensions ---

class TestComplexityDimensions:
    def test_create_with_valid_values(self) -> None:
        dims = ComplexityDimensions(
            scope=50,
            dependencies=30,
            ambiguity=70,
            risk=20,
            novelty=60,
        )
        assert dims.scope == 50
        assert dims.dependencies == 30
        assert dims.ambiguity == 70
        assert dims.risk == 20
        assert dims.novelty == 60

    def test_clamp_above_100(self) -> None:
        dims = ComplexityDimensions(
            scope=150,
            dependencies=200,
            ambiguity=101,
            risk=999,
            novelty=100,
        )
        assert dims.scope == 100
        assert dims.dependencies == 100
        assert dims.ambiguity == 100
        assert dims.risk == 100
        assert dims.novelty == 100

    def test_clamp_below_0(self) -> None:
        dims = ComplexityDimensions(
            scope=-10,
            dependencies=-1,
            ambiguity=-50,
            risk=-100,
            novelty=0,
        )
        assert dims.scope == 0
        assert dims.dependencies == 0
        assert dims.ambiguity == 0
        assert dims.risk == 0
        assert dims.novelty == 0

    def test_boundary_values_unchanged(self) -> None:
        dims = ComplexityDimensions(
            scope=0,
            dependencies=100,
            ambiguity=50,
            risk=1,
            novelty=99,
        )
        assert dims.scope == 0
        assert dims.dependencies == 100
        assert dims.ambiguity == 50
        assert dims.risk == 1
        assert dims.novelty == 99

    def test_defaults_to_zero(self) -> None:
        dims = ComplexityDimensions()
        assert dims.scope == 0
        assert dims.dependencies == 0
        assert dims.ambiguity == 0
        assert dims.risk == 0
        assert dims.novelty == 0


# --- ComplexityScore ---

class TestComplexityScore:
    def test_shallow_tier(self) -> None:
        score = ComplexityScore(
            score=20,
            tier=ForgeTier.SHALLOW,
            dimensions=ComplexityDimensions(scope=20, dependencies=15, ambiguity=10, risk=5, novelty=30),
        )
        assert score.score == 20
        assert score.tier == ForgeTier.SHALLOW

    def test_default_empty_lists(self) -> None:
        score = ComplexityScore(
            score=50,
            tier=ForgeTier.STANDARD,
            dimensions=ComplexityDimensions(),
        )
        assert score.similar_plans == []
        assert score.reused_patterns == []

    def test_similar_plans_populated(self) -> None:
        score = ComplexityScore(
            score=80,
            tier=ForgeTier.DEEP,
            dimensions=ComplexityDimensions(scope=80),
            similar_plans=["plan-abc", "plan-xyz"],
        )
        assert len(score.similar_plans) == 2
        assert "plan-abc" in score.similar_plans

    def test_reused_patterns_populated(self) -> None:
        score = ComplexityScore(
            score=60,
            tier=ForgeTier.STANDARD,
            dimensions=ComplexityDimensions(novelty=60),
            reused_patterns=["phase-gate", "quality-gate"],
        )
        assert "phase-gate" in score.reused_patterns

    def test_all_tiers_accepted(self) -> None:
        for tier in ForgeTier:
            score = ComplexityScore(
                score=50,
                tier=tier,
                dimensions=ComplexityDimensions(),
            )
            assert score.tier == tier
