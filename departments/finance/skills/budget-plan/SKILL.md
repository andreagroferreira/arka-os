---
name: fin/budget-plan
description: >
  Budget planning with Helena (CFO): revenue plan, cost structure, headcount
  and CAPEX by department using the FP&A cycle plus zero-based budgeting,
  delivering an annual/quarterly budget with department breakdowns and
  approval thresholds. TRIGGER: "orçamento anual", "orçamento do Q3",
  "budget plan", "plano de custos por departamento", "headcount budget",
  "/fin budget". SKIP: cash timing, runway or burn questions ->
  fin/cashflow-forecast (forecasts cash movement, not spend allocation);
  full P&L/Balance Sheet projections -> fin/financial-model (3-statement
  modelling, not budget approval).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Budget Plan — `/fin budget <scope>`

> **Agent:** Helena (CFO) | **Framework:** FP&A Cycle + Zero-Based Budgeting

## What It Does

Budget planning: revenue plan, cost structure, headcount, CAPEX by department.

## Output

Annual/quarterly budget with department breakdowns and approval thresholds
