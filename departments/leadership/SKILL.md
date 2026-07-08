---
name: arka-lead
description: >
  Leadership & People department. Team health, hiring, feedback culture, performance
  management, coaching. Frameworks: Five Dysfunctions, Radical Candor, OKRs, Netflix Culture.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Leadership & People — ArkaOS v2

> **Squad Lead:** Rodrigo (Leadership Director) | **Agents:** 2 | **Topology:** Enabling

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/lead disc <person/team>` | DISC behavioral assessment | Specialist |
| `/lead team-build <context>` | Team composition design | Enterprise |
| `/lead 1on1 <person>` | 1-on-1 meeting agenda preparation | Specialist |
| `/lead feedback <person>` | Structured feedback (Radical Candor) | Specialist |
| `/lead okr <scope>` | OKR definition and cascade | Focused |
| `/lead culture` | Culture audit and design | Enterprise |
| `/lead review <person>` | Performance review preparation | Focused |
| `/lead conflict <situation>` | Conflict resolution plan | Focused |
| `/lead hiring <role>` | Hiring plan with scorecard | Focused |
| `/lead change <initiative>` | Change management plan | Enterprise |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Rodrigo** | 1 | I+S | Leadership strategy, OKRs, team assessment |
| **Paula** | 2 | S+I | Performance coaching, feedback, conflict mediation |

## Frameworks: Five Dysfunctions (Lencioni), Radical Candor (Scott), OKRs (Doerr), Netflix Culture (Hastings), Who Method (hiring), DISC Adaptation, Keeper Test

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch model: constitution `quality_gate.model_policy` (single source — best-available via Model Fabric; veto is model-independent)
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
