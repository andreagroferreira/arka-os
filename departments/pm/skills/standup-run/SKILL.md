---
name: pm/standup-run
description: >
  Runs a structured daily standup — what was done, what's next, blockers —
  focused on flow and unblocking rather than status theatre; outputs a
  summary with blockers flagged and actions assigned. TRIGGER: "run the
  standup", "faz o standup", "daily standup", "ponto de situação da
  equipa", "quais os bloqueios", "/pm standup". SKIP: sprint-boundary
  ceremonies (item selection, goal, commitment) -> pm/sprint-plan; board
  flow policies and WIP limits behind recurring blockers -> pm/kanban-setup
  (fix the system, not the meeting).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Standup Run — `/pm standup`

> **Agent:** Jorge (Scrum Master) | **Framework:** Structured Daily Standup

## What It Does

Run structured standup: what done, what next, blockers. Flow-focused, not status.

## Output

Standup summary with blockers flagged and actions assigned
