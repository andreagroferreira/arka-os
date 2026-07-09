---
name: landing/awareness-diagnose
description: >
  Diagnose where the audience sits on Schwartz's 5 awareness levels
  (unaware, problem, solution, product, most aware) plus traffic
  temperature, and recommend the matching copy framework. TRIGGER:
  "awareness level", "nível de consciência do público", "o público conhece
  o produto?", "traffic temperature", "que framework de copy usar",
  "/landing awareness". SKIP: actually writing the copy once the level is
  known -> landing/copy-framework (it applies the framework; this skill
  only diagnoses).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Awareness Diagnose — `/landing awareness <traffic>`

> **Agent:** Teresa (Sales Copywriter) | **Framework:** Schwartz 5 Awareness Levels

## What It Does

Diagnose audience awareness level: unaware, problem, solution, product, most aware.

## Output

Awareness diagnosis with recommended copy framework and traffic temperature
