# 19 · Token Economy

← [Home](Home.md) · [18 · Integrations & Tools](18-Integrations-and-Tools.md) · [20 · For Everyone](20-For-Everyone.md)

How ArkaOS spends, measures, and saves tokens. Three layers: **routing**
(best model for the job), **telemetry** (every token counted), and
**governance** (the CostGovernor is the only hard ceiling). Full detail:
[docs/TOKEN-ECONOMY.md](../docs/TOKEN-ECONOMY.md).

## The spending posture

Quality-critical work — design, review, architecture, strategy, specs,
ADRs, Quality Gate reviews, Forge complex/super tiers — runs the **best
model available at maximum effort** by default (Excellence Reform,
2026-07-05). Cost optimisation never downgrades a quality phase. Only
genuinely mechanical work (commit messages, changelog, keyword
extraction, formatting) runs cheap/local.

`~/.arkaos/models.yaml` (Model Fabric) is the operator-owned source of
truth; the packaged default is `config/models.yaml`. The
`model-routing` Constitution rule enforces the posture.

## Telemetry — every token counted

`core/runtime/llm_cost_telemetry.py` records every call — including
cached tokens — to `~/.arkaos/telemetry/llm-cost.jsonl`. Rollups feed
`/arka costs` (day/week/month, per provider/model/session, cache hit
rate) and `/arka status` (24h cost + cache hit rate + call count).
Visibility-first per ADR-011: budgets are informational, not
restrictive — except the CostGovernor.

## CostGovernor — the only hard ceiling

Opt-in per project (`.arkaos.json`): `hardCapUsd` (per session),
`dailyCapUsd` (per day), `hardDeny` (deny vs warn). It is the ONLY
ceiling that can downgrade a quality phase — never a cost-optimisation
preference.

## Context economy

- **Synapse** — 12-layer injection at ~87 ms with relevance filtering:
  empty layers are skipped, so context stays tight.
- **ContextCompactor** — compresses turns into ~600-token summaries.
- **Token Hygiene hook** — 4 non-blocking checks per prompt: context
  monitor (>60% suggest, >80% warn), topic drift, large paste,
  vague reference.
- **Subagent discipline** — dispatch only for real isolation needs
  (>3 reads, >5 greps); trivial work stays on the main thread.
  Quality dispatches are exempt.

## Model Fabric and the gateway

The LiteLLM gateway (`core/runtime/gateway/`) makes role→model routing
physically take effect: mixed mode (quality → Anthropic-direct,
execution → local Ollama in one session) or local-only (everything on
the local model, keyless). Gateway failure degrades to a plain launch.

## Read further

[docs/TOKEN-ECONOMY.md](../docs/TOKEN-ECONOMY.md) · `docs/adr/` ADR-011
(cost-governor) and ADR 2026-07-04 (evidence flow) · `config/models.yaml`
