---
name: sales/forecast-revenue
description: >
  Builds a revenue forecast from probability-weighted pipeline, historical
  stage conversion, and confidence intervals, with forecast-accuracy metrics.
  TRIGGER: "revenue forecast", "previsão de receita", "quanto vamos fechar
  este trimestre?", "forecast do pipeline", "/sales forecast". SKIP:
  diagnosing velocity, bottlenecks, or deal aging -> sales/pipeline-manage
  (pipeline health, not the revenue number); cash-in/cash-out or longer-range
  financial projections -> finance/cashflow-forecast.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Forecast Revenue — `/sales forecast`

> **Agent:** Ines S. (Sales Ops) | **Framework:** Pipeline Velocity + Revenue Forecasting

## What It Does

Revenue forecast: weighted pipeline, historical conversion, confidence intervals.

## Output

Revenue forecast with probability-weighted pipeline and accuracy metrics
