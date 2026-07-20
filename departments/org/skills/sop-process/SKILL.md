---
name: org/sop-process
description: >
  Creates a Standard Operating Procedure: numbered step-by-step procedure with
  roles, tools, exceptions, ownership, and a review schedule (SOP Lifecycle).
  TRIGGER: "documenta este processo", "cria um SOP de RH", "SOP for
  onboarding", "procedimento passo-a-passo", "process documentation", "/org
  sop <process>". SKIP: operational and Lean procedures owned by the ops
  department -> ops/sop-create (same artifact, ops-domain processes);
  automating the process instead of documenting it -> ops/workflow-automate.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Sop Process — `/org sop <process>`

> **Agent:** Carla (People Ops) | **Framework:** SOP Lifecycle + Process Documentation

## What It Does

SOP creation: step-by-step procedures with roles, tools, exceptions.

## Output

SOP document with numbered steps, ownership, and review schedule
