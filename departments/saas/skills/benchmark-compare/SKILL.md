---
name: saas/benchmark-compare
description: >
  Compares your SaaS metrics against industry quartiles (KeyBanc + Meritech
  benchmarks) and delivers a traffic-light report with improvement
  priorities. TRIGGER: "compare com benchmarks do setor", "estamos acima da
  média?", "how do my SaaS metrics compare", "benchmark my churn/NRR",
  "quartis da indústria", "/saas benchmark". SKIP: KPIs not yet defined or
  tracked -> saas/metrics-dashboard (build the metrics stack before
  comparing it); a below-benchmark churn number needing root causes ->
  saas/churn-analysis (diagnosis, not comparison).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Benchmark Compare — `/saas benchmark`

> **Agent:** Rita S. (Metrics Analyst) | **Framework:** KeyBanc + Meritech SaaS Benchmarks

## What It Does

Benchmark comparison: compare your metrics against industry quartiles.

## Output

Benchmark report with traffic-light indicators and improvement priorities
