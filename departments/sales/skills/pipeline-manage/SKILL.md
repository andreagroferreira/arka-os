---
name: sales/pipeline-manage
description: >
  Analyses pipeline health with the Pipeline Velocity formula: velocity,
  conversion by stage, deal aging, bottlenecks, and forecast accuracy.
  TRIGGER: "análise do pipeline", "pipeline review", "onde estão presos os
  deals?", "conversão por fase", "pipeline velocity", "/sales pipeline". SKIP:
  the revenue number with confidence intervals -> sales/forecast-revenue;
  deep-dive on one deal -> sales/deal-qualify; delivery or task boards rather
  than sales stages -> pm/kanban-setup.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Pipeline Manage — `/sales pipeline`

> **Agent:** Ines S. (Sales Ops) | **Framework:** Pipeline Velocity Formula

## What It Does

Pipeline analysis: velocity, conversion by stage, deal aging, forecast accuracy.

## Output

Pipeline report with velocity metrics, bottlenecks, and forecast
