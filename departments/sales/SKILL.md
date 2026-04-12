---
name: arka-sales
description: >
  Sales & Negotiation department. Pipeline management, proposals, discovery calls,
  deal qualification, negotiation. Frameworks: SPIN Selling, Challenger Sale, MEDDIC.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Sales & Negotiation — ArkaOS v2

> **Squad Lead:** Miguel (Sales Director) | **Agents:** 2

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/sales pipeline` | Pipeline analysis and recommendations | Focused |
| `/sales proposal <client>` | Sales proposal writing | Focused |
| `/sales discovery <prospect>` | Discovery call preparation (SPIN questions) | Focused |
| `/sales qualify <deal>` | Deal qualification (BANT/MEDDIC) | Specialist |
| `/sales objection <objection>` | Objection handling playbook | Specialist |
| `/sales negotiate <deal>` | Negotiation strategy (BATNA) | Focused |
| `/sales forecast` | Revenue forecast | Specialist |
| `/sales spin <context>` | SPIN selling preparation | Specialist |
| `/sales challenger <context>` | Challenger sale approach | Specialist |
| `/sales pricing <product>` | Pricing negotiation strategy | Focused |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Miguel** | 1 | D+I | Sales strategy, pipeline, forecasting |
| **Joao** | 2 | D+I | Closing, objection handling, negotiation |

## Frameworks: SPIN Selling (Rackham), Challenger Sale (Dixon), MEDDIC/BANT, Sandler, BATNA, Pipeline Velocity Formula

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
