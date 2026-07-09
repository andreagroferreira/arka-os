---
name: saas/churn-analysis
description: >
  Diagnoses churn with cohort breakdowns, retention curves, and root-cause
  churn reasons, ending in a prevention plan. TRIGGER: "churn analysis",
  "análise de churn", "porque estamos a perder clientes", "retention
  curves", "cohort retention", "/saas churn". SKIP: pass/fail retention
  check before approving acquisition spend -> saas/leaky-bucket (gate
  verdict, not diagnosis); collecting qualitative customer feedback ->
  saas/voc-loop (voice signal, not cohort math); saving individual at-risk
  accounts -> saas/customer-success.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Churn Analysis — `/saas churn`

> **Agent:** Rita S. (Metrics Analyst) | **Framework:** Cohort Analysis + Retention Curves

## What It Does

Churn analysis: cohort breakdown, retention curves, churn reasons, prevention plan.

## Output

Churn report with cohort data, root causes, and intervention recommendations
