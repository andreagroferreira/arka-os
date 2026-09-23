"""Static pricing table for cost telemetry.

This file contains a static lookup table of known model identifiers to
their public per-token pricing. It is used to compute an optional
`estimated_cost_usd` attached to telemetry records. It does NOT drive
any model-selection logic — that is explicitly forbidden by the
LLM-agnostic contract.

Snapshot 2026-09-03 (Runtime Sync PR-2), Opus 5.5 rows added 2026-09-22:
values sourced from the public
Anthropic pricing page (https://platform.claude.com/docs/en/about-claude/pricing) and
OpenAI (https://openai.com/api/pricing). Refresh when model families
change. Unknown models return `None` from `estimate_cost_usd` and are
logged with a null cost — never a guessed number.
"""

from __future__ import annotations

# USD per 1M tokens. Only the `cache_read` and `cache_write` keys apply
# to providers that expose prompt caching (currently Anthropic; rates
# are the 0.1x / 1.25x input multipliers for 5-minute cache writes).
# Missing keys fall back to 0 cost contribution rather than raising —
# which is exactly why an UNKNOWN model id must be surfaced loudly
# (native_usage marks `pricing_status: unknown-model`; /arka status warns):
# on 2026-09-03 every Fable 5.1 row was costing $0.00 in silence.
PRICING: dict[str, dict[str, float]] = {
    # Claude Fable 5.1 (2026-09-01): $10/$50 per MTok, cache reads $0.25
    # (75% below Fable 5), 5m cache writes $12.50 — all from the public
    # pricing page as of 2026-09-03. 1M context is native.
    "claude-fable-5-1": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 0.25,
        "cache_write": 12.50,
    },
    "claude-fable-5-1[1m]": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 0.25,
        "cache_write": 12.50,
    },
    # Claude Mythos 5.1 — same underlying model and rate card as Fable 5.1,
    # restricted access (limited availability per the pricing page). Priced
    # so the estimator never returns None for a legitimately served row.
    "claude-mythos-5-1": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 0.25,
        "cache_write": 12.50,
    },
    "claude-fable-5": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 1.00,
        "cache_write": 12.50,
    },
    # [1m] context-window alias seen in native transcripts — Fable 5's
    # 1M window is the default at the same published rate.
    "claude-fable-5[1m]": {
        "input": 10.00,
        "output": 50.00,
        "cache_read": 1.00,
        "cache_write": 12.50,
    },
    # Snapshot 2026-09-22 (Opus 5.5 sweep): $4 / $20 per MTok and cache
    # reads at $0.20 (0.05x input) per the public pricing page; the Claude
    # Code 2.1.280 alias `opus` resolves here, so this is the lane every
    # `model: opus` agent runs on. cache_write is NOT published yet: 5.00
    # is the standard 1.25x five-minute multiplier — the same assumption
    # the Fable 5.1 row shipped with — replace it when the page lists it.
    # 1M context is native; the [1m] alias prices the same.
    "claude-opus-5-5": {
        "input": 4.00,
        "output": 20.00,
        "cache_read": 0.20,
        "cache_write": 5.00,
    },
    "claude-opus-5-5[1m]": {
        "input": 4.00,
        "output": 20.00,
        "cache_read": 0.20,
        "cache_write": 5.00,
    },
    # History — snapshot 2026-08-09 (Gate Economy PR-8): drop-in at Opus
    # 4.8's rates per the official model catalog — 1M context is the
    # default with NO long-context premium, so the [1m] alias prices the
    # same. The row was missing while claude-opus-5 carried 28% of weekly
    # input tokens, pricing them at $0.00 and blinding the CostGovernor.
    # Retained so 2026-08/09 sessions stay priced; the live lane is
    # claude-opus-5-5 above.
    "claude-opus-5": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    "claude-opus-5[1m]": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25,
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
    # $2/$10 is the STANDARD list price: the pricing page (2026-09-03) states
    # the increase scheduled for 2026-09-01 will not occur.
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
    # TypeSafe JEV 1.13 (typed decisions, not an LLM) — OpenRouter model
    # page, 2026-09: $0.042 per MTok of input, output tokens free. The
    # smoke test of 2026-09-23 confirmed output_tokens billed at 0. The
    # endpoint echoes a dated id (typesafe/jev-1.13-20260917); callers
    # price by the REQUESTED id, the dated row keeps the echo priced too.
    "typesafe/jev-1.13": {"input": 0.042, "output": 0.0},
    "typesafe/jev-1.13-20260917": {"input": 0.042, "output": 0.0},
    "jev-1.13.0": {"input": 0.042, "output": 0.0},
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
