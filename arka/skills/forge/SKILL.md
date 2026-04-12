---
name: arka-forge
description: >
  The Forge — ArkaOS intelligent multi-agent planning engine. Complexity-based
  escalation, critic synthesis, visual companion, Obsidian persistence.
  Analyses any prompt across 5 dimensions, routes to 1-3 explorer subagents,
  runs a critic synthesis, and produces an approved ForgePlan before execution.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# The Forge — ArkaOS Intelligent Planning Engine

> **Engine:** `core/forge/` | **Plans stored:** `~/.arkaos/plans/` | **Obsidian:** `ArkaOS/Forge/`

The Forge analyses any prompt across 5 complexity dimensions, routes to 1-3 explorer subagents for independent plans, runs a critic to synthesize the best plan, and persists an approved ForgePlan before execution. Every plan enforces Constitution rules (branch isolation, spec-driven, QA, Quality Gate, Obsidian output).

## Commands

| Command | Description | When to use |
|---------|-------------|-------------|
| `/forge <prompt>` | Forge a new plan | Any task you want planned before executing |
| `/forge resume` | Resume approved plan | After a session break, repo drift, or restart |
| `/forge status` | Show active forge status | Check what plan is currently active |
| `/forge history` | List all past plans | Browse plans saved in `~/.arkaos/plans/` |
| `/forge show <id>` | Show plan detail | Inspect a specific plan by ID |
| `/forge compare <id1> <id2>` | Compare two plans side-by-side | Evaluate alternative approaches |
| `/forge patterns` | List extracted patterns | See reusable patterns from past plans |
| `/forge cancel` | Cancel active forge | Discard current plan without executing |

## Complexity Tiers

| Tier | Score | Explorers | Critic | Companion | Model |
|------|-------|-----------|--------|-----------|-------|
| Simple (Shallow) | ≤ 30 | 1 (Pragmatic, inline) | Light | None | haiku |
| Standard | 31-65 | 2 (Pragmatic + Architectural, parallel) | Full | On request | sonnet |
| Complex (Deep) | 66-85 | 3 (+ Contrarian, parallel) | Full | Proactive | opus |
| Super | ≥ 86 | 3 + full synthesis | Full (highest judgment) | Proactive | opus |

Five dimensions score 0-100 each: **scope**, **dependencies**, **ambiguity**, **risk**, **novelty**. See `references/complexity-engine.md` for scoring details and tier confirmation prompt.

## Subagent Dispatch — Model Routing

When dispatching explorer subagents via the Task tool, include `model: <tier_model>` parameter. The tier-to-model mapping is:

- simple → `model: haiku` (fast routing, single explorer)
- standard → `model: sonnet` (default, 1-2 explorers)
- complex → `model: opus` (3 explorers + critic synthesis)
- super → `model: opus` (highest judgment, full synthesis)

Example: for complex tier, use `model: opus` on every explorer Task call and on the critic synthesis dispatch.

## Explorer Lenses

| Lens | Question | Role |
|------|----------|------|
| Pragmatic | "What is the simplest thing that works?" | Minimum viable, reuse-first, collapse phases |
| Architectural | "What is the right way to build this long-term?" | SOLID/DDD/Clean Arch, testability, no tech debt |
| Contrarian | "What is everyone missing or assuming wrongly?" | Stress-test assumptions, surface hidden risk |

Full lens prompts and the Critic synthesis prompt live in `references/critic-synthesis.md`.

## Orchestration Overview

Every `/forge <prompt>` executes a 10-step flow: (1) context snapshot, (2) Obsidian knowledge check, (3) complexity analysis, (4) tier confirmation gate, (5) launch explorers in parallel, (6) critic synthesis on anonymized outputs, (7) render terminal plan, (8) user decision (Approve / Revise / Companion / Detail / Quit), (9) handoff with repo-drift check, (10) persist to YAML + Obsidian and extract patterns.

Revisions re-run the critic only (not explorers), capped at 5. Secondary commands (`resume`, `status`, `history`, `show`, `compare`, `patterns`, `cancel`) operate on persisted plans in `~/.arkaos/plans/`.

**See `references/workflows.md` for the full step-by-step flows, revision flow, secondary commands, and Constitution enforcement rules.**

## Plan ID Format

Plan IDs follow the format: `forge-YYYYMMDD-<4-char hex>` (example: `forge-20260411-a3f2`).

```python
import hashlib, datetime
date = datetime.date.today().strftime("%Y%m%d")
suffix = hashlib.md5(prompt.encode()).hexdigest()[:4]
plan_id = f"forge-{date}-{suffix}"
```

## References

- `references/workflows.md` — Full 10-step main flow, revision flow, secondary commands, Constitution compliance
- `references/complexity-engine.md` — Complexity scoring, dimensions, tier thresholds, tier confirmation prompt
- `references/critic-synthesis.md` — Explorer preamble and 3 lens instructions, Critic subagent synthesis prompt
