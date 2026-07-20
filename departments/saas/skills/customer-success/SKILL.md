---
name: saas/customer-success
description: >
  Builds a customer success playbook across the lifecycle — onboard, adopt,
  expand, renew, advocate — with health score model, touchpoint cadence,
  and expansion plays (Lincoln Murphy). TRIGGER: "customer success
  playbook", "plano de sucesso do cliente", "health score dos clientes",
  "renewal and expansion plan", "gerir contas em risco", "/saas cs
  <account>". SKIP: aggregate churn numbers and cohorts ->
  saas/churn-analysis (metrics diagnosis, not account playbooks);
  self-serve signup activation -> saas/onboarding-optimize (product
  onboarding, not managed accounts).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Customer Success — `/saas cs <account>`

> **Agent:** Patricia (CS Manager) | **Framework:** Customer Success Lifecycle (Lincoln Murphy)

## What It Does

Customer success playbook: onboard, adopt, expand, renew, advocate.

## Output

CS playbook with health score model, touchpoint cadence, and expansion plays
