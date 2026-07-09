---
name: sales/objection-handle
description: >
  Builds an objection-handling playbook for a specific sales objection:
  acknowledge, clarify, respond with evidence, confirm, plus follow-up moves.
  TRIGGER: "objection handling", "o cliente diz que é caro", "como respondo a
  esta objeção?", "handle this objection", "/sales objection <objection>".
  SKIP: recurring price pushback needing value anchors and margin defence ->
  sales/pricing-negotiate; full multi-issue negotiation prep with concessions
  and walk-away -> sales/negotiate-plan.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Objection Handle — `/sales objection <objection>`

> **Agent:** Joao (Sales Closer) | **Framework:** Objection Handling Matrix

## What It Does

Handle sales objection: acknowledge, clarify, respond with evidence, confirm.

## Output

Objection handling playbook with responses, evidence points, and follow-up
