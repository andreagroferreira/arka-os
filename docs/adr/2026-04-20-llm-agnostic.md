---
id: ADR-2026-04-20-llm-agnostic
title: LLM Agnostic Auto-Documentor — No Model Hardcoding
status: accepted
date: 2026-04-20
deciders: Andre Groferreira (owner), Marco (CTO), Marta (CQO), Paulo (Dev Lead)
related:
  - docs/adr/2026-04-20-kb-first-intelligence.md
  - docs/adr/2026-04-20-flow-marker-v2.md
  - core/runtime/llm_provider.py
  - core/runtime/pricing.py
  - core/runtime/llm_cost_telemetry.py
  - core/cognition/auto_documentor.py
---

# ADR — LLM Agnostic Auto-Documentor

## Status

Accepted — 2026-04-20

## Context

ArkaOS v2.21.0 shipped the KB-First Intelligence Loop with `auto_documentor`
using a `_call_llm` stub that returned the empty string, falling through
to a template synthesiser. The template produces adequate notes but not
great — and the whole point of the loop is that the vault compounds with
high-quality learnings, daily.

The first instinct was to wire the Anthropic SDK, pick haiku/sonnet/opus
via a `choose_model` heuristic based on content complexity, and ship.
Owner rejected this outright:

> "nao quero modelos tem que ser automatico independentmente do model."

Auto-documentor must NOT know the model. Whatever runtime the user has
(Claude Code with Opus, Codex with GPT-4, Gemini CLI with Gemini 2.5,
Cursor with whatever), ArkaOS uses it. Runtime decides. ArkaOS delegates.

This ADR is the follow-up to ADR-2026-04-20-kb-first-intelligence
(intelligence v2) and specifically addresses the LLM wiring gap it left
open.

## Decision drivers

1. **Zero model hardcoding.** No `if model == "opus"`, no `choose_model`,
   no branching on model names in logic. Only a static `PRICING` table
   may mention model names (as keys for cost lookup, not as routing).
2. **Multi-runtime parity.** ADR-001 (Multi-Runtime Agnostic) set the
   direction. This ADR extends it: LLM synthesis must work under all
   four supported runtimes (Claude Code, Codex CLI, Gemini CLI, Cursor).
3. **Async worker context.** The `auto_doc_worker` runs outside any live
   Claude session — it cannot use the `Task` tool. Therefore the provider
   must use each runtime's **headless CLI** (`claude -p`, `codex exec`,
   `gemini -p`) or a direct SDK when appropriate.
4. **Prompt caching is ON by default** where the provider supports it.
   5-min TTL Anthropic prompt caching reduces repeat-synthesis cost by
   ~90% when the system prompt is stable.
5. **Budget telemetry per ADR-011.** Informational, not restrictive.
   Every call logs to `~/.arkaos/telemetry/llm-cost.jsonl`;
   `/arka costs` aggregates; advisory warns at $5/session; never blocks.
6. **Template fallback preserved.** If the provider is unavailable,
   raises, or returns empty, the template synthesiser still runs. Notes
   are degraded but the loop never breaks.

## Alternatives considered

### Alt A — Direct Anthropic SDK with `choose_model` heuristic

Hardcode haiku/sonnet/opus routing in `choose_model(learning)` based on
content length + keyword heuristics. Call Anthropic SDK directly.

- Pros: simple, one dependency, works today.
- Cons: locks ArkaOS to Anthropic; contradicts ADR-001 (multi-runtime);
  explicitly rejected by owner.
- **Rejected.**

### Alt B — Environment variable drives model name

Keep direct Anthropic SDK; read `ANTHROPIC_MODEL` from env. No
`choose_model` in code.

- Pros: no hardcoding; user controls model.
- Cons: still locked to Anthropic; no support for Codex/Gemini/Cursor
  users.
- **Partially adopted** as the `anthropic-direct` provider — one of three.

### Alt C — Runtime-delegated subagent dispatch (adopted)

Abstract behind `LLMProvider` Protocol. `SubagentProvider` (default)
detects the active runtime via `core/runtime/registry.active_runtime()`
and shells out to that runtime's headless CLI. The runtime decides the
model from its own config — ArkaOS never passes one.

- Pros: true multi-runtime; zero model hardcoding; user's environment
  decides everything.
- Cons: headless CLI support varies by runtime (Claude Code has
  `claude -p --output-format json`; Codex and Gemini CLI flags need
  verification; Cursor has no headless mode).
- **Adopted** as the default provider, with anthropic-direct as the
  fallback and stub as the last resort.

### Alt D — Multi-provider abstraction with explicit user selection

Ship all providers; user picks via config. No default; raise if unset.

- Pros: explicit; no surprises.
- Cons: onboarding friction; breaks zero-config upgrades.
- **Rejected** as default but adopted as a manual override via
  `llm.provider` config key.

## Decision

Adopt **Alt C + Alt B + template fallback**:

### Three providers behind one Protocol

```python
@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, *, max_tokens: int, system: str) -> LLMResponse: ...
    def is_available(self) -> bool: ...
    def name(self) -> str: ...
```

| Provider | Default | Model decided by | Behaviour when unavailable |
|---|---|---|---|
| `subagent` | ✅ | Active runtime's headless CLI (Claude Code, Codex, Gemini, Cursor) | Fall to `anthropic-direct` |
| `anthropic-direct` | — | `ANTHROPIC_MODEL` env var; no code default | Fall to `stub` |
| `stub` | tests only | N/A (template fallback) | Always available |

### Fallback chain

`get_llm_provider()` reads `~/.arkaos/config.json` `llm.provider` (default
`"subagent"`). If the configured provider reports `is_available() == False`,
fall through: `subagent → anthropic-direct → stub`. Each fallback is
logged to the same telemetry JSONL with `provider: "fallback:<from>→<to>"`.

### `RuntimeAdapter.headless_complete`

Added to `core/runtime/base.py` as a concrete method with a default raise.
Per-runtime overrides:
- `claude_code.py` — implemented via `claude -p --output-format json`
- `codex_cli.py` — `NotImplementedError` with TODO(llm-agnostic) pending
  CLI syntax verification
- `gemini_cli.py` — `NotImplementedError` with TODO(llm-agnostic) pending
  CLI syntax verification
- `cursor.py` — `NotImplementedError` (no headless mode exists)

A runtime without headless support triggers the fallback chain in
`SubagentProvider`.

### Prompt caching

- `AnthropicDirectProvider` uses Anthropic native caching
  (`cache_control: {"type": "ephemeral"}`) on the system block. 5-min TTL.
- `SubagentProvider` inherits the runtime's own caching behaviour
  (Claude Code's `claude -p` already caches).
- `StubProvider` returns empty — cache is irrelevant.

### Cost telemetry

Every successful call appends one JSON line to
`~/.arkaos/telemetry/llm-cost.jsonl`:

```json
{
  "ts": "...",
  "session_id": "...",
  "provider": "subagent",
  "model": "(runtime)",
  "tokens_in": 1234,
  "tokens_out": 567,
  "cached_tokens": 890,
  "estimated_cost_usd": 0.0123
}
```

`/arka costs [today|week|month|all|sessions]` aggregates. Soft advisory
when any session exceeds $5 USD equivalent. Never blocks.

### Auto-documentor wiring

`core/cognition/auto_documentor.py`:
- `choose_model()` deleted.
- `model_hint` parameter removed from every signature.
- `_call_llm(learning)` delegates to `get_llm_provider().complete(...)`.
- On provider unavailable, exception, or empty response, falls through
  to the existing `_template_synthesize` path.
- The note body suffix drops any model reference —
  `"Auto-documented by ArkaOS"`.

### Static guard

A test (`test_no_model_names_in_auto_documentor_source` and
`test_no_hardcoded_model_in_llm_provider_source`) greps the production
files for `opus|sonnet|haiku|gpt-4|gemini` (case-insensitive) and asserts
zero matches outside the `PRICING` table.

## Rollout

`v2.22.0` stable (no beta label per owner preference for v2.21.0+).
Feature flag: `llm.provider` defaults to `"subagent"`. Users without
auto-doc enabled see zero behaviour change. Users with auto-doc enabled
get real LLM synthesis automatically on upgrade — the runtime they
already use decides the model.

Kill switches:
- Set `llm.provider: "stub"` to revert to template synthesiser.
- Unset `ANTHROPIC_MODEL` to prevent `anthropic-direct` provider.

## Consequences

### Positive

- ArkaOS is genuinely runtime-agnostic: the user's model choice in their
  runtime config is the single source of truth for synthesis model.
- Auto-documentor note quality jumps from "adequate template" to "real
  LLM synthesis" for most users, automatically on upgrade.
- Budget telemetry gives full visibility across every LLM call, per
  session, per model, per provider, with cache hit rate.
- Prompt caching on by default reduces cost by ~90% for repeat syntheses
  of similar sessions.
- `choose_model` is permanently deleted; future engineers cannot
  accidentally hardcode a model.
- Three-layer fallback (subagent → anthropic-direct → stub) keeps the
  loop running even when one layer fails.

### Negative

- Codex and Gemini CLI headless paths ship as `NotImplementedError` until
  someone with local installs verifies the invocation syntax. Users on
  those runtimes will see `SubagentProvider` fall through to
  `anthropic-direct` or `stub`.
- `AnthropicDirectProvider` requires users to set `ANTHROPIC_MODEL` env
  var — no default. Documented in release notes; graceful
  `is_available=False` when unset.
- Three providers widen the test matrix. Mitigated by mock-based tests.

### Neutral

- `anthropic` SDK is optional (lazy import). Users who never enable
  `anthropic-direct` never need to install it.
- Pricing table in `core/runtime/pricing.py` must be updated when
  providers change their rates. Unknown models log `cost=null` —
  accurate, not silently wrong.

## Test evidence

- `tests/python/test_llm_provider.py` — provider selection, fallback
  chain, subagent dispatch, anthropic-direct with prompt caching, stub
  fallback, static no-hardcoding guard
- `tests/python/test_llm_cost_telemetry.py` — atomic append, concurrent
  writers, summarise by period, by provider, by session, advisories
- `tests/python/test_llm_cost_telemetry_cli.py` — `/arka costs` CLI
  invocations
- `tests/python/test_pricing.py` — known-model lookup, unknown→null
- `tests/python/test_auto_documentor.py` — provider delegation, template
  fallback, static no-model-names guard
- Full suite: green at merge commit.

## References

- ADR-001 — Multi-Runtime Agnostic Architecture
- ADR-011 — Token budgets informational, not restrictive
- ADR-2026-04-20-kb-first-intelligence — parent épico
- `~/.arkaos/plans/2026-04-20-llm-agnostic.md` — canonical plan
- Obsidian: `[[2026-04-20 LLM Agnostic — Auto-Documentor]]`,
  `[[ArkaOS v2 Architecture Decisions]]`
