"""Static pricing table for cost telemetry.

This file contains a static lookup table of known model identifiers to
their public per-token pricing. It is used to compute an optional
`estimated_cost_usd` attached to telemetry records. It does NOT drive
any model-selection logic — that is explicitly forbidden by the
LLM-agnostic contract.

TODO(pricing-snapshot 2026-04-20): values sourced from the public
Anthropic (https://www.anthropic.com/pricing) and OpenAI
(https://openai.com/api/pricing) pricing pages. Refresh when model
families change. Unknown models return `None` from `estimate_cost_usd`
and are logged with a null cost — never a guessed number.
"""

from __future__ import annotations


# USD per 1M tokens. Only the `cache_read` and `cache_write` keys apply
# to providers that expose prompt caching (currently Anthropic). Missing
# keys fall back to 0 cost contribution rather than raising.
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00,
    },
    "gpt-4": {
        "input": 30.00,
        "output": 60.00,
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
    },
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 5.00,
    },
}


def estimate_cost_usd(
    model: str,
    tokens_in: int,
    tokens_out: int,
    cached_tokens: int = 0,
) -> float | None:
    """Return the estimated USD cost for the given usage, or None.

    Returns None when the model is not in `PRICING` — the caller should
    emit a null cost in telemetry rather than guess. All inputs are
    clamped to non-negative.
    """
    row = PRICING.get(model)
    if row is None:
        return None
    tin = max(0, int(tokens_in))
    tout = max(0, int(tokens_out))
    tcached = max(0, int(cached_tokens))
    # cached tokens are a subset of input tokens; charge them at the
    # reduced cache-read rate and only charge the remainder at input.
    tinput_paid = max(0, tin - tcached)
    cost = 0.0
    cost += tinput_paid * row.get("input", 0.0) / 1_000_000
    cost += tout * row.get("output", 0.0) / 1_000_000
    cost += tcached * row.get("cache_read", 0.0) / 1_000_000
    return round(cost, 8)


def known_models() -> list[str]:
    return sorted(PRICING.keys())
