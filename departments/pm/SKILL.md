---
name: arka-pm
description: >
  Project & Product Management department. Product discovery, sprint management,
  roadmapping, estimation, stakeholders. Frameworks: Scrum, Kanban, Shape Up,
  Continuous Discovery (Teresa Torres), Monte Carlo forecasting.
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

# Project & Product Management — ArkaOS v2

> **Squad Lead:** Carolina (Product Manager) | **Agents:** 3

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/pm sprint <action>` | Sprint planning, review, or retrospective | Focused |
| `/pm discover <opportunity>` | Product discovery (OST, interviews, experiments) | Enterprise |
| `/pm roadmap <product>` | Outcome-driven product roadmap | Enterprise |
| `/pm retro` | Facilitated retrospective | Specialist |
| `/pm estimate <scope>` | Estimation and Monte Carlo forecasting | Focused |
| `/pm backlog <action>` | Backlog grooming and prioritization (RICE) | Focused |
| `/pm story <description>` | User story writing with INVEST + acceptance criteria | Specialist |
| `/pm risk <project>` | Risk register and pre-mortem | Focused |
| `/pm stakeholder <project>` | Stakeholder mapping (Power/Interest grid) | Specialist |
| `/pm kanban <action>` | Kanban board setup with WIP limits | Focused |
| `/pm shape <feature>` | Shape Up pitch with appetite and rabbit holes | Enterprise |
| `/pm standup` | Structured daily standup | Specialist |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Carolina** | 1 | I+C | Product vision, discovery, outcome-driven roadmaps |
| **Sara** (PO) | 2 | I+C | Backlog, stories, acceptance criteria, prioritization |
| **Jorge** (SM) | 2 | S+I | Facilitation, flow metrics, retros, coaching |

## Frameworks: Scrum (Sutherland), Kanban (Anderson), Shape Up (Singer), Continuous Discovery (Torres), OST, RICE/WSJF, Monte Carlo (Vacanti), User Story Mapping (Patton), Impact Mapping (Adzic), INVEST

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
