---
name: arka-org
description: >
  Organization & Teams department. Org design, team topologies, scaling operations,
  hiring plans, onboarding, compensation. Frameworks: Team Topologies, Spotify Model.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Organization & Teams — ArkaOS v2

> **Squad Lead:** Sofia (COO, Tier 0) | **Agents:** 1 | **Topology:** Platform

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/org design <company>` | Organizational structure design | Enterprise |
| `/org hiring <role>` | Hiring plan with job spec and scorecard | Focused |
| `/org onboarding <role>` | Employee onboarding program design | Focused |
| `/org remote` | Remote work setup and policies | Focused |
| `/org meeting audit` | Meeting optimization (reduce, restructure) | Specialist |
| `/org sop <process>` | SOP creation for organizational processes | Specialist |
| `/org culture` | Culture definition document | Enterprise |
| `/org assess <team>` | Team assessment (health, skills, gaps) | Focused |
| `/org comp <role>` | Compensation plan and benchmarking | Specialist |
| `/org decide <decision>` | Decision framework (RACI, authority matrix) | Specialist |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Sofia** (COO) | 0 | S+C | Org strategy, cross-department coordination, scaling |

## Frameworks: Team Topologies (Skelton/Pais), Spotify Model (Kniberg), Five Dysfunctions (Lencioni), OKRs (Doerr), Netflix Culture, Conway's Law, RACI Matrix

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch model: constitution `quality_gate.model_policy` (single source — best-available via Model Fabric; veto is model-independent)
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
