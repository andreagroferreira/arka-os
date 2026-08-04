# ArkaOS Token Economy

> How ArkaOS spends, measures, and saves tokens. The economy has three
> layers: **routing** (best model for the job), **telemetry** (every
> token counted), and **governance** (the CostGovernor is the only
> hard ceiling).

## The spending posture

The Excellence Reform (2026-07-05) sets a quality-first default:
quality-critical work — design, review, architecture, strategy, specs,
ADRs, Quality Gate reviews, Forge complex/super tiers — runs the **best
model available at maximum effort** by default. Cost optimisation never
downgrades a quality phase. The ONLY exception is genuinely mechanical
work (commit messages, changelog, keyword extraction, data fetching,
formatting), which runs haiku-class/local.

This is enforced by the `model-routing` Constitution rule and the Model
Fabric (`core/runtime/model_router.py`): `~/.arkaos/models.yaml` is the
operator-owned source of truth; the packaged default ships at
`config/models.yaml`. Roles govern dispatch — resolve("review") →
best-effort frontier, resolve("mechanical") → cheap/local.

## Telemetry — every token counted

`core/runtime/llm_cost_telemetry.py` records each LLM call with cached
tokens and costs to `~/.arkaos/telemetry/llm-cost.jsonl` (thread-safe
locked append). Rollups (`read_entries`, period buckets) feed:

- `/arka costs` — spend by day/week/month, provider/model/session,
  top expensive sessions, cache hit rate
- `/arka status` — 24h cost line + cache hit rate + call count
- `mcp_telemetry` — MCP server call volumes
- `enforcement_telemetry` — hook/gate block rates

Everything is visibility-first (ADR-011: budgets are informational, not
restrictive) — except the CostGovernor.

## CostGovernor — the only hard ceiling

`core/runtime/cost_governor.py` is an **opt-in** enforcement layer over
the telemetry. Configured per project via `.arkaos.json`:

```json
{"budget": {"hardCapUsd": 20.0, "dailyCapUsd": 50.0, "hardDeny": false}}
```

- `hardCapUsd` — per-session cap (matched on `session_id`)
- `dailyCapUsd` — cap over today's total spend
- `hardDeny` — when true, an exceeded cap DENIES (hook exit 2);
  otherwise it warns `[arka:warn] budget cap exceeded ...`

The quality-first posture holds under it: the CostGovernor hard budget
is the ONLY ceiling that can downgrade a quality phase — never a
cost-optimisation preference.

## Context economy

- **Synapse v2** — 12-layer context injection at ~87 ms cold / ~83 ms
  warm with relevance filtering: layers that return nothing are skipped,
  so context stays tight instead of always-full.
- **ContextCompactor** (`core/runtime/context_compactor.py`) — compresses
  conversation turns into ~600-token summaries, capping the context
  surface of long sessions.
- **Token Hygiene hook** (UserPromptSubmit, 4 checks, 6000 ms in-hook
  budget, never blocking): context-usage monitor (>60% suggest, >80%
  warn), topic-drift detection, large-paste detection, vague-reference
  detection. Suggestions only — the operator decides.
- **Subagent discipline** — dispatch a subagent only when a task needs
  >3 reads, >5 greps, or isolated context; trivial tasks stay on the
  main thread to avoid handoff overhead. Quality dispatches (QG
  reviewers, adversarial verification) are exempt — independent review
  context is a correctness requirement.

## Model Fabric and the gateway

The gateway layer (`core/runtime/gateway/`, LiteLLM proxy rendered from
`models.yaml`) makes role→model routing physically take effect by
pointing Claude Code at the proxy. Two modes: mixed (quality →
Anthropic-direct, execution → local Ollama, in one session) and
local-only (everything on the local Ollama model, keyless). Any gateway
failure degrades to a plain `claude` launch.

## Read further

- `core/runtime/model_router.py` — the Model Fabric
- `core/runtime/cost_governor.py` — the budget gate
- `core/runtime/llm_cost_telemetry.py` — the ledger
- `core/runtime/context_compactor.py` — the compressor
- `config/models.yaml` — the packaged role→model defaults
- `docs/adr/` — ADR-011 (budgets informational)
