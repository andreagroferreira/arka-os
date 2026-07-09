---
name: saas/mvp-build
description: >
  Defines MVP scope: core feature set, activation metric, time-to-value
  target, and acceptance criteria for a SaaS first version. TRIGGER:
  "define o MVP", "MVP scope", "que features entram na v1", "what goes in
  the first version", "métrica de ativação do MVP", "/saas mvp <product>".
  SKIP: generating the actual project code -> saas/saas-scaffold (files and
  stack, not scope); idea not yet validated -> saas/validate-idea (validate
  before scoping); formal implementation spec for the dev squad -> dev/spec
  (engineering requirements, not product scope).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Mvp Build — `/saas mvp <product>`

> **Agent:** Tiago (SaaS Strategist) | **Framework:** MVP Scoping + Activation Metrics

## What It Does

MVP scope definition: core features, activation metric, time-to-value target.

## Output

MVP spec with feature set, acceptance criteria, and activation definition
