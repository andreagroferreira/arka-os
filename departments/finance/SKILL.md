---
name: arka-fin
description: >
  Finance & Investment department. Financial modeling, valuation, unit economics,
  fundraising, risk management, FP&A. Frameworks: 3-Statement Model, DCF (Damodaran),
  Unit Economics, COSO ERM, Venture Deals (Brad Feld).
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

# Finance & Investment — ArkaOS v2

> **Squad Lead:** Helena (CFO, Tier 0) | **Agents:** 3

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/fin model <type>` | Financial model (3-statement, DCF, scenario) | Enterprise |
| `/fin report <type>` | Financial report (monthly, quarterly, annual) | Focused |
| `/fin cashflow <period>` | Cash flow forecast | Focused |
| `/fin budget <scope>` | Budget planning | Focused |
| `/fin unit-economics` | Unit economics analysis (CAC, LTV, Rule of 40) | Focused |
| `/fin pitch <stage>` | Investor pitch deck financials | Enterprise |
| `/fin valuation` | Company valuation (DCF, comparables) | Enterprise |
| `/fin expense-audit` | Expense audit and optimization | Specialist |
| `/fin revenue-model` | Revenue model design | Focused |
| `/fin scenario <context>` | Scenario analysis (base, bull, bear) | Focused |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Helena** (CFO) | 0 | D+C | Strategy, capital allocation, risk governance |
| **Leonor** | 2 | C+S | Financial modeling, unit economics, scenarios |
| **Rui** | 2 | D+I | Fundraising, term sheets, cap table, M&A |

## Frameworks: 3-Statement Model, DCF (Damodaran), Unit Economics (SaaS), COSO ERM, FP&A Cycle, VC Framework (Feld), Scenario Analysis, Monte Carlo

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
