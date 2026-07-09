---
name: ops/sop-create
description: >
  Creates a Standard Operating Procedure: numbered steps, RACI roles, tools, exceptions,
  and review cycle, following the SOP Lifecycle and Lean. TRIGGER: "cria um SOP",
  "documenta o processo", "create SOP", "standard operating procedure", "procedimento
  operacional", "/ops sop <process>". SKIP: automating the process instead of documenting
  it -> ops/workflow-automate (a running flow, not a document); team delivery process and
  ceremonies -> pm/kanban-setup or pm/sprint-plan.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Sop Create — `/ops sop <process>`

> **Agent:** Daniel (Ops Lead) | **Framework:** SOP Lifecycle + Lean

## What It Does

Create a Standard Operating Procedure: steps, roles, tools, exceptions, review cycle.

## Output

SOP document with numbered steps, RACI, tools, exceptions, and review schedule
