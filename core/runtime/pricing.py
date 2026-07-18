"""Static pricing table for cost telemetry.

This file contains a static lookup table of known model identifiers to
their public per-token pricing. It is used to compute an optional
`estimated_cost_usd` attached to telemetry records. It does NOT drive
any model-selection logic — that is explicitly forbidden by the
LLM-agnostic contract.

Snapshot 2026-07-18: values sourced from the public Anthropic pricing
page (https://platform.claude.com/docs/en/about-claude/pricing) and
OpenAI (https://openai.com/api/pricing). Refresh when model families
change. Unknown models return `None` from `estimate_cost_usd` and are
logged with a null cost — never a guessed number.
"""

from __future__ import annotations


# USD per 1M tokens. Only the `cache_read` and `cache_write` keys apply
# to providers that expose prompt caching (currently Anthropic; rates
# are the 0.1x / 1.25x input multipliers for 5-minute cache writes).
# Missing keys fall back to 0 cost contribution rather than raising.
PRICING: dict[str, dict[str, float]] = {
    "claude-fable-5": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 1.00,
        "cache_write": 12.50,
    },
    "claude-opus-4-8": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    "claude-opus-4-7": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    "claude-opus-4-6": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    "claude-opus-4-5": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    # Introductory pricing ($2/$10) is in effect through 2026-08-31;
    # from 2026-09-01 the standard rate is $3/$15 (cache $0.30/$3.75).
    # Refresh this row when the introductory window closes.
    "claude-sonnet-5": {
        "input": 2.00,
        "output": 10.00,
        "cache_read": 0.20,
        "cache_write": 2.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
    # Generic (undated) alias of the dated haiku row above — native
    # transcripts sometimes report the tier id without the date suffix.
    # Same published price; NOT an invented number.
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write": 1.25,
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
