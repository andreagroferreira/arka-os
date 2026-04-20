---
name: ops/sop-create
description: >
  Create a Standard Operating Procedure: steps, roles, tools, exceptions, review cycle.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Sop Create — `/ops sop <process>`

> **Agent:** Daniel (Ops Lead) | **Framework:** SOP Lifecycle + Lean

## What It Does

Create a Standard Operating Procedure: steps, roles, tools, exceptions, review cycle.

## Output

SOP document with numbered steps, RACI, tools, exceptions, and review schedule
