---
name: ops/metrics-dashboard
description: >
  Defines the operational metrics system — throughput, lead time, error rate, SLAs —
  producing a spec with the OMTM, targets, and alerting rules. TRIGGER: "métricas
  operacionais", "define os KPIs de operações", "track SLAs", "operational metrics",
  "OMTM", "/ops metrics". SKIP: designing and rendering the dashboard surface ->
  ops/dashboard-build (layout and widgets; this skill picks the numbers); production
  telemetry and tracing -> dev/observability.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Metrics Dashboard — `/ops metrics`

> **Agent:** Daniel (Ops Lead) | **Framework:** Operational Metrics + OMTM

## What It Does

Operational metrics dashboard: throughput, lead time, error rate, SLAs.

## Output

Ops dashboard spec with OMTM, targets, and alerting rules
