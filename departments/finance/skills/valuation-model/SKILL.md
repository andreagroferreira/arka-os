---
name: fin/valuation-model
description: >
  Company valuation: DCF with WACC (Damodaran), comparable company
  analysis and precedent transactions, producing a valuation range with
  multiples and sensitivity analysis. TRIGGER: "quanto vale a empresa",
  "valuation", "avaliação da empresa", "DCF", "múltiplos comparáveis",
  "/fin valuation". SKIP: building the projections the DCF discounts ->
  fin/financial-model (valuation consumes its outputs); designing the
  business model itself -> strategy/bmc (Business Model Canvas, not
  enterprise value); presenting the number to investors ->
  fin/pitch-deck.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Valuation Model — `/fin valuation`

> **Agent:** Leonor (Financial Analyst) | **Framework:** DCF (Damodaran) + Comparables

## What It Does

Company valuation: DCF with WACC, comparable company analysis, precedent transactions.

## Output

Valuation range with DCF, multiples, and sensitivity analysis
