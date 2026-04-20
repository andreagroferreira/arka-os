---
name: arka-saas
description: >
  SaaS & Micro-SaaS department. Covers the full lifecycle: idea validation, MVP scoping,
  pricing, PLG, metrics, growth, customer success, and scaling. From solo founder
  ($50K Micro-SaaS) to T2D3 trajectories ($100M+ ARR).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# SaaS & Micro-SaaS Department — ArkaOS v2

> **Squad Lead:** Tiago (SaaS Strategist) | **Agents:** 3
> **Frameworks:** SaaS Metrics Stack, PLG, Micro-SaaS Playbook, T2D3, Van Westendorp

## Commands

| Command | Description | Workflow Tier |
|---------|-------------|---------------|
| `/saas validate <idea>` | Idea validation (30-day framework) | Enterprise |
| `/saas mvp <product>` | MVP scope definition with acceptance criteria | Focused |
| `/saas niche <market>` | Niche evaluation (staircase stage, competition) | Focused |
| `/saas metrics` | SaaS metrics dashboard setup (MRR, churn, NRR) | Focused |
| `/saas pricing <product>` | Pricing strategy (Van Westendorp, value-based) | Focused |
| `/saas plg <product>` | Product-Led Growth setup (freemium/trial) | Enterprise |
| `/saas cs <account>` | Customer success playbook | Focused |
| `/saas growth <stage>` | Growth plan by stage (seed, series A, scale) | Enterprise |
| `/saas gtm <product>` | Go-to-market strategy for SaaS | Enterprise |
| `/saas launch` | Launch checklist and execution plan | Enterprise |
| `/saas stack` | Micro-SaaS stacking strategy | Focused |
| `/saas onboard <product>` | Onboarding flow optimization | Focused |
| `/saas churn` | Churn analysis with RFM and cohort data | Specialist |
| `/saas benchmark` | Benchmark comparison (KeyBanc, Meritech) | Specialist |

## Squad

| Agent | Role | Tier | DISC |
|-------|------|------|------|
| **Tiago** | SaaS Strategist — Metrics, PLG, pricing | 1 | D+C |
| **Andre S.** | Growth Engineer — Experiments, activation, loops | 2 | D+I |
| **Patricia** | CS Manager — Lifecycle, churn prevention, NRR | 2 | S+I |

## Key Metrics (always tracked)

| Metric | Target | Framework |
|--------|--------|-----------|
| LTV:CAC | > 3:1 | Unit Economics |
| CAC Payback | < 12 months | Unit Economics |
| NRR | > 110% | Customer Success |
| Rule of 40 | Growth% + Margin% > 40% | Brad Feld |
| Gross Churn | < 10% annual (SMB) | SaaS Metrics |
| Activation Rate | > 40% in 7 days | PLG |

## Frameworks Applied

| Framework | Author | Used For |
|-----------|--------|---------|
| SaaS Metrics Stack | Christoph Janz | Growth, efficiency, durability metrics |
| PLG Flywheel | Wes Bush | Product-led acquisition + retention |
| Micro-SaaS Playbook | Rob Walling | Validation, niche selection, bootstrapping |
| T2D3 Growth | Christoph Janz | Scaling trajectory planning |
| Van Westendorp | Van Westendorp | Pricing sensitivity analysis |
| Value-Based Pricing | Patrick Campbell | Pricing based on willingness to pay |
| Customer Success Lifecycle | Lincoln Murphy | Onboard, adopt, expand, renew, advocate |
| AARRR / RARRA | Dave McClure | Growth funnel metrics |

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
