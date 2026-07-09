---
name: fin/cashflow-forecast
description: >
  Cash flow forecasting across operating, investing and financing flows,
  with runway, burn rate and working-capital analysis (Leonor, Financial
  Analyst — Cash Flow Management + FP&A). TRIGGER: "cashflow forecast",
  "previsão de tesouraria", "quanto runway temos", "burn rate", "fluxo de
  caixa", "/fin cashflow". SKIP: allocating spend by department or
  headcount -> fin/budget-plan (budgeting, not cash timing); full
  3-statement projections -> fin/financial-model (cash flow is one
  statement of three); stress-testing assumptions best/worst case ->
  fin/scenario-analysis.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Cashflow Forecast — `/fin cashflow <period>`

> **Agent:** Leonor (Financial Analyst) | **Framework:** Cash Flow Management + FP&A

## What It Does

Cash flow forecast: operating, investing, financing flows with runway calculation.

## Output

Cash flow forecast with runway, burn rate, and working capital analysis
