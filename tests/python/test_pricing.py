"""Smoke tests for the static pricing lookup table."""

from __future__ import annotations

from core.runtime.pricing import PRICING, estimate_cost_usd, known_models


class TestEstimateCostUsd:
    def test_known_model_returns_number(self):
        cost = estimate_cost_usd("claude-opus-4-7", 1_000_000, 0)
        assert cost == 5.0

    def test_output_tokens_priced(self):
        cost = estimate_cost_usd("claude-opus-4-7", 0, 1_000_000)
        assert cost == 25.0

    def test_cached_tokens_billed_at_discount(self):
        # 1M cache-read tokens only — Opus cache_read rate is $0.50/M.
        cost = estimate_cost_usd(
            "claude-opus-4-7", tokens_in=1_000_000, tokens_out=0, cached_tokens=1_000_000
        )
        assert cost == 0.5

    def test_current_generation_models_priced(self):
        # The models the Model Fabric routes to must never return None.
        assert estimate_cost_usd("claude-opus-4-8", 1_000_000, 0) == 5.0
        assert estimate_cost_usd("claude-sonnet-5", 1_000_000, 0) == 2.0
        assert estimate_cost_usd("claude-fable-5", 0, 1_000_000) == 50.0

    def test_unknown_model_returns_none(self):
        assert estimate_cost_usd("some-unreleased-model", 1000, 1000) is None

    def test_negative_tokens_clamped_to_zero(self):
        # Safety: negative inputs must not produce negative cost.
        cost = estimate_cost_usd("gpt-4", -5, -5)
        assert cost == 0.0

    def test_known_models_contains_seeded_entries(self):
        known = known_models()
        assert "claude-opus-4-7" in known
        assert "gpt-4" in known
        assert "gemini-2.5-pro" in known

    def test_pricing_values_are_positive(self):
        for model, row in PRICING.items():
            for key, value in row.items():
                assert value > 0, f"{model}.{key} should be positive"


class TestOpus5Pricing:
    """Gate Economy PR-8: claude-opus-5 carried 28% of weekly input
    tokens at $0.00 attributed because the row was missing."""

    def test_opus5_rows_present_with_published_rates(self):
        for model in ("claude-opus-5", "claude-opus-5[1m]"):
            row = PRICING[model]
            assert row["input"] == 5.00
            assert row["output"] == 25.00
            assert row["cache_read"] == 0.50
            assert row["cache_write"] == 6.25

    def test_opus5_estimate_is_not_none(self):
        cost = estimate_cost_usd("claude-opus-5", 1_000_000, 100_000, 0)
        assert cost == 5.00 + 2.50

    def test_fable_1m_alias_present(self):
        assert PRICING["claude-fable-5[1m]"]["input"] == 10.00


class TestFable51Rows:
    """Runtime Sync PR2 (2026-09-03): the model the operator runs is priced."""

    def test_fable_5_1_and_1m_alias_are_priced(self):
        from core.runtime import pricing

        for mid in ("claude-fable-5-1", "claude-fable-5-1[1m]", "claude-mythos-5-1"):
            row = pricing.PRICING[mid]
            assert row["input"] == 10.00 and row["output"] == 50.00
            assert row["cache_read"] == 0.25  # 75% below the previous Fable rate
            assert pricing.estimate_cost_usd(mid, 1_000_000, 100_000) is not None

    def test_sonnet_5_is_standard_list_price(self):
        from core.runtime import pricing

        row = pricing.PRICING["claude-sonnet-5"]
        assert (row["input"], row["output"]) == (2.00, 10.00)
