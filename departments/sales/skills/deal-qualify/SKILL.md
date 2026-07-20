---
name: sales/deal-qualify
description: >
  Qualifies a deal with MEDDIC/BANT — Metrics, Economic Buyer, Decision
  Criteria, Decision Process, Champion — into a scorecard with a go/no-go
  recommendation. TRIGGER: "qualifica este lead", "qualify this deal", "vale a
  pena este negócio?", "MEDDIC", "BANT", "/sales qualify <deal>". SKIP: health
  of the whole funnel -> sales/pipeline-manage (stage conversion and aging
  across all deals); preparing the first conversation before qualification
  data exists -> sales/discovery-call.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Deal Qualify — `/sales qualify <deal>`

> **Agent:** Ines S. (Sales Ops) | **Framework:** MEDDIC / BANT Qualification

## What It Does

Deal qualification: Metrics, Economic Buyer, Decision Criteria, Process, Champion.

## Output

Deal qualification scorecard with go/no-go recommendation
