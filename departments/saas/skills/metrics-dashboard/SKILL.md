---
name: saas/metrics-dashboard
description: >
  Sets up SaaS metrics tracking (Janz SaaS Metrics Stack): KPI definitions,
  data sources, dashboard layout, targets, and alert thresholds. TRIGGER:
  "metrics dashboard", "define os KPIs do SaaS", "métricas do produto",
  "track MRR/churn/LTV", "setup metrics tracking", "/saas metrics-setup".
  SKIP: KPIs already tracked and you want to compare against industry
  quartiles -> saas/benchmark-compare (comparison, not setup);
  marketing/funnel performance reporting -> marketing/analytics-report;
  LTV/CAC economics modelling -> finance/unit-economics.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Metrics Dashboard — `/saas metrics-setup`

> **Agent:** Rita S. (Metrics Analyst) | **Framework:** SaaS Metrics Stack (Janz)

## What It Does

Set up SaaS metrics tracking: define KPIs, data sources, dashboard layout.

## Output

Metrics dashboard spec with KPI definitions, targets, and alert thresholds
