---
name: arka-costs
description: >
  LLM cost visibility — aggregates `~/.arkaos/telemetry/llm-cost.jsonl` by
  day/week/month/all, breaks down by provider/model/session, surfaces top
  expensive sessions and cache hit rate. Visibility-only per ADR-011;
  never imposes hard caps.
allowed-tools: [Bash, Read]
---

# /arka costs — LLM cost visibility

Aggregates runtime-agnostic LLM call telemetry written by
`core/runtime/llm_cost_telemetry.record_cost`. Per ADR-011, token
budgets are **informational, not restrictive** — this command only
surfaces usage and emits soft advisories. It never blocks a call.

## Usage

| Command | What it shows |
| --- | --- |
| `/arka costs` | Today (UTC midnight → now) |
| `/arka costs today` | Same as above |
| `/arka costs week` | Rolling last 7 days |
| `/arka costs month` | Rolling last 30 days |
| `/arka costs all` | Entire history in the JSONL |
| `/arka costs sessions` | Top 10 most expensive sessions (all time) |

## Output

- Total cost (USD, `n/a` when all entries are unpriced models)
- Total tokens in / out, plus cached tokens
- Cache hit rate (`cached / tokens_in`)
- Breakdown by provider
- Breakdown by model (`<unknown>` bucket for calls with no model)
- Top 10 sessions sorted by cost
- Advisories — a soft line per session that crossed the
  `advisory_threshold_usd` (default $5 per session)

## Implementation

This skill shells out to the Python CLI:

```bash
~/.arkaos/bin/arka-py -m core.runtime.llm_cost_telemetry_cli <period>
```

Source:
- `core/runtime/llm_cost_telemetry.py` — `summarise`, `list_expensive_sessions`
- `core/runtime/llm_cost_telemetry_cli.py` — markdown renderer

## Data source

`~/.arkaos/telemetry/llm-cost.jsonl` (override with `ARKA_LLM_COST_PATH`).
One JSONL line per LLM call, written by every provider adapter.
Malformed lines are skipped and counted, never raised.

## Cost-tuning levers

Outside this skill's scope but worth surfacing alongside the summary:

| Lever | Where | Effect |
| --- | --- | --- |
| `ARKAOS_LLM_PROVIDER` | env | Switch between Anthropic, OpenAI, Gemini adapters per the multi-LLM router. |
| `ANTHROPIC_BEDROCK_SERVICE_TIER` | env (Claude Code 2.1.122+) | `default` / `flex` / `priority`. Only relevant when routing through AWS Bedrock — `flex` cuts cost ~50 % on non-urgent workloads at the price of higher tail latency. |
| Agent `model:` field | `departments/*/agents/*.yaml` | Per-agent override per the model-routing matrix in CLAUDE.md. Mechanical roles default to haiku, C-suite to opus. |
| Quality Gate model | constitution rule (NON-NEGOTIABLE) | Marta / Eduardo / Francisca always run on opus regardless of the cost ceiling. |

## Non-negotiables

1. Read-only. This skill never edits state.
2. No hard budget caps — advisories are strings, not errors.
3. No external dependencies; stdlib only.
