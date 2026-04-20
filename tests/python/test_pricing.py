"""Smoke tests for the static pricing lookup table."""

from __future__ import annotations

from core.runtime.pricing import PRICING, estimate_cost_usd, known_models


class TestEstimateCostUsd:
    def test_known_model_returns_number(self):
        cost = estimate_cost_usd("claude-opus-4-7", 1_000_000, 0)
        assert cost == 15.0

    def test_output_tokens_priced(self):
        cost = estimate_cost_usd("claude-opus-4-7", 0, 1_000_000)
        assert cost == 75.0

    def test_cached_tokens_billed_at_discount(self):
        # 1M cache-read tokens only — Opus cache_read rate is $1.50/M.
        cost = estimate_cost_usd(
            "claude-opus-4-7", tokens_in=1_000_000, tokens_out=0, cached_tokens=1_000_000
        )
        assert cost == 1.5

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
