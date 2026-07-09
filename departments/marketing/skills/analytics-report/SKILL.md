---
name: mkt/analytics-report
description: >
  Marketing analytics report: AARRR pirate-metrics funnel, channel
  performance breakdown, and CAC trends for a given period. TRIGGER:
  "relatório de marketing", "analytics report", "como estão as métricas
  de marketing", "AARRR", "CAC por canal", "/mkt analytics <period>".
  SKIP: designing or instrumenting the AARRR growth loop itself (not
  reporting on it) -> mkt/growth-loop (builds the loop; this skill reports
  the metrics); store or e-commerce sales analytics -> ecom/analytics (owns
  revenue and product metrics); content platform performance ->
  content/analytics; funnel step conversion diagnosis ->
  landing/funnel-metrics.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Analytics Report — `/mkt analytics <period>`

> **Agent:** Luna (Marketing Director) | **Framework:** AARRR Pirate Metrics

## What It Does

Marketing analytics report: AARRR funnel, channel performance, CAC trends.

## Output

Analytics dashboard with AARRR metrics and channel breakdown
