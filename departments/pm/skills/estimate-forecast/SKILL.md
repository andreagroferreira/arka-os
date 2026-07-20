---
name: pm/estimate-forecast
description: >
  Estimation and delivery forecasting: story points, throughput analysis,
  and Monte Carlo simulation producing confidence intervals (50th/85th/95th
  percentile) for "when will it be done". TRIGGER: "quando fica pronto",
  "estima este backlog", "when will this ship", "forecast the release
  date", "Monte Carlo forecast", "/pm estimate". SKIP: sizing items during
  refinement -> pm/backlog-groom (estimation inside grooming, not
  probabilistic forecasting); committing capacity for a single sprint ->
  pm/sprint-plan; quantifying code-quality drag on delivery ->
  dev/tech-debt (debt economics, not schedule forecasting).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Estimate Forecast — `/pm estimate <scope>`

> **Agent:** Jorge (Scrum Master) | **Framework:** Monte Carlo Forecasting (Vacanti)

## What It Does

Estimation and forecasting: story points, throughput, Monte Carlo probability.

## Output

Forecast with confidence intervals (50th, 85th, 95th percentile)
