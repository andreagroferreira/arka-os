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
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Refactor Plan — `/dev refactor <scope>`

> **Agent:** Paulo (Tech Lead) | **Framework:** Refactoring Catalog (Martin Fowler)

## What It Does

Plan a refactoring: identify code smells, select refactoring patterns, ensure test safety net.

When the `codebase-memory` MCP is active, ground the plan in the real
structure BEFORE proposing moves: `get_architecture` for the module
map, `trace_path` for every call-site the refactor touches (impact
analysis), `search_graph` to find duplicated implementations worth
consolidating. The graph is a prior — verify with Read before planning
an edit.

## Output

Refactoring plan with patterns, risk assessment, and test verification steps
