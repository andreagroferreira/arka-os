import pytest
from core.forge.schema import ForgeTier, ComplexityDimensions
from core.forge.complexity import (
    score_dimensions,
    calculate_weighted_score,
    determine_tier,
    analyze_complexity,
)


class TestScoreDimensions:
    def test_high_scope_many_files(self):
        dims = score_dimensions("Refactor entire engine", [f"f{i}.py" for i in range(10)], ["dev", "ops"], [], [])
        assert dims.scope >= 70

    def test_low_scope_single_file(self):
        dims = score_dimensions("Fix typo", ["README.md"], ["dev"], [], [])
        assert dims.scope <= 30

    def test_novelty_decreases_with_similar_plans(self):
        dims_novel = score_dimensions("Add module", ["m.py"], ["dev"], [], [])
        dims_familiar = score_dimensions("Add module", ["m.py"], ["dev"], ["plan-1", "plan-2"], ["pat-1"])
        assert dims_familiar.novelty < dims_novel.novelty

    def test_ambiguity_increases_with_vague_prompt(self):
        dims_clear = score_dimensions(
            "Add retry to core/api/client.py with exponential backoff max 3",
            ["core/api/client.py"],
            ["dev"],
            [],
            [],
        )
        dims_vague = score_dimensions("make it better", [], [], [], [])
        assert dims_vague.ambiguity > dims_clear.ambiguity

    def test_risk_increases_with_security_keywords(self):
        dims = score_dimensions(
            "Modify authentication and encryption",
            ["core/security/auth.py"],
            ["dev"],
            [],
            [],
        )
        assert dims.risk >= 60


class TestCalculateWeightedScore:
    def test_all_100(self):
        assert calculate_weighted_score(
            ComplexityDimensions(scope=100, dependencies=100, ambiguity=100, risk=100, novelty=100)
        ) == 100

    def test_all_zero(self):
        assert calculate_weighted_score(ComplexityDimensions()) == 0

    def test_scope_weight_30_pct(self):
        assert calculate_weighted_score(ComplexityDimensions(scope=100)) == 30


class TestDetermineTier:
    def test_shallow(self):
        assert determine_tier(0) == ForgeTier.SHALLOW
        assert determine_tier(30) == ForgeTier.SHALLOW

    def test_standard(self):
        assert determine_tier(31) == ForgeTier.STANDARD
        assert determine_tier(65) == ForgeTier.STANDARD

    def test_deep(self):
        assert determine_tier(66) == ForgeTier.DEEP
        assert determine_tier(100) == ForgeTier.DEEP


class TestAnalyzeComplexity:
    def test_returns_complete_score(self):
        result = analyze_complexity(
            "Build full system",
            [f"f{i}.py" for i in range(8)],
            ["dev", "ops"],
            [],
            [],
        )
        assert 0 <= result.score <= 100
        assert result.tier in list(ForgeTier)
        assert result.dimensions.scope >= 0
