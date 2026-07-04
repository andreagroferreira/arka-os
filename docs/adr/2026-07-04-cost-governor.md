---
id: ADR-2026-07-04-cost-governor
title: CostGovernor — Enforceable Budget Caps, Advisory by Default
status: accepted
date: 2026-07-04
deciders: Andre Groferreira (owner), Marco (CTO), Helena (CFO), Paulo (Dev Lead)
related:
  - docs/adr/2026-04-20-llm-agnostic.md
  - docs/strategy/2026-05-27-arkaos-runtime-strategy.md
  - core/runtime/cost_governor.py
  - core/runtime/llm_cost_telemetry.py
  - core/runtime/llm_retry.py
  - config/hooks/pre-tool-use.sh
---

# ADR — CostGovernor: Enforceable Budget Caps, Advisory by Default

## Status

Accepted — 2026-07-04. **Extends ADR-011 without revoking it.**

## Context

ADR-011 established that token budgets are "informational, not
restrictive": `llm_cost_telemetry` records every call, `/arka costs`
surfaces the aggregates, and advisories are soft strings. That stance is
correct as a default — an OS that silently kills its operator's work
over a dollar threshold is worse than one that overspends.

Two things changed:

1. **The native blind spot closed.** The Stop hook now records real
   per-turn Claude Code usage (`native:session` rows via
   `core/runtime/native_usage.py`), so telemetry finally reflects the
   bulk of actual spend, not just the `llm_provider` sliver. Caps over
   under-reported data would have been theater; caps over real data are
   meaningful.
2. **Operator goal: "um prompt → entrega de alto valor" without dying
   mid-project.** Goal-mode schedules (`--goal`/`--task-budget`) and
   retry-on-429 (`llm_retry.py`) make long unattended runs viable — and
   unattended runs need a cost ceiling the operator chose in advance.

The 2026-05-27 runtime strategy (§6.3.2) proposed a full CostGovernor
with per-task/workflow/project scopes and downgrade routing. That is the
end state; this ADR ships the enforceable minimum.

## Decision

`core/runtime/cost_governor.py` with three config knobs under
`~/.arkaos/config.json → budget`:

| Key | Meaning | Default |
|---|---|---|
| `hardCapUsd` | per-session cap (matched on `session_id`) | absent = no cap |
| `dailyCapUsd` | cap over today's total recorded spend | absent = no cap |
| `hardDeny` | exceeded cap DENIES the tool call (exit 2) | `false` = WARN only |

- `check(session_id) -> GovernorDecision(allow, reason, spent_usd,
  cap_usd)`; spend read from `llm_cost_telemetry` (session rows summed
  directly; daily via `summarise(period="today")`).
- CLI: `python -m core.runtime.cost_governor <session_id> [--json]`,
  exit 0 allow / 3 deny.
- Hook wiring: the check piggy-backs on the existing flow_enforcer
  python heredoc in `config/hooks/pre-tool-use.sh` (no extra process).
  Exceeded caps emit `[arka:warn] budget cap exceeded ($X of $Y)` on
  stderr; the structured `permissionDecision: deny` path (flow_enforcer's
  mechanism) fires ONLY when `budget.hardDeny=true`.

## Fail-open invariants (NON-NEGOTIABLE within this module)

- No `budget` config, null caps, unparsable config → **allow** (ADR-011
  advisory stance preserved, fully backward compatible).
- Telemetry file missing/corrupt → **allow**. Never block on missing
  data — an empty ledger means "nothing recorded", not "over budget".
- Governor import/runtime error inside the hook → **allow**.

## Consequences

- Operators who configure nothing see zero behavior change.
- Operators who set caps get a visible `[arka:warn]` the moment a
  session or day crosses the line — mid-run, on the next effect tool.
- Operators who additionally set `hardDeny: true` get a real circuit
  breaker: the session cannot mutate anything further until they raise
  the cap or start a new session (per-session scope) / day rolls over.
- Deferred to the full strategy §6.3.2 build: per-task/workflow/project
  scopes, `soft_limit_pct` early warning, and `on_exceed: downgrade`
  model rerouting (depends on the ModelRouter, which does not exist yet).
