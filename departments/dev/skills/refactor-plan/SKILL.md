---
name: dev/refactor-plan
description: >
  Plan a refactoring with Martin Fowler's catalog: identify code smells,
  select refactoring patterns, assess risk, and ensure a test safety net
  before touching code. TRIGGER: "refactor", "refatora isto", "limpa este
  código", "code smells", "melhora a estrutura", "clean up this module", "/dev
  refactor"; load BEFORE restructuring existing code. SKIP: reviewing a diff
  or PR for quality -> dev/clean-code-review (a verdict on code, not a
  restructuring plan); systemic debt inventory and prioritization ->
  dev/tech-debt; new feature work -> dev/spec first.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Refactor Plan — `/dev refactor <scope>`

> **Agent:** Paulo (Tech Lead) | **Framework:** Refactoring Catalog (Martin Fowler)

## What It Does

Plan a refactoring: identify code smells, select refactoring patterns, ensure test safety net.

## Output

Refactoring plan with patterns, risk assessment, and test verification steps
