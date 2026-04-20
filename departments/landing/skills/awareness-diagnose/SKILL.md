---
name: landing/awareness-diagnose
description: >
  Diagnose audience awareness level: unaware, problem, solution, product, most aware.
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

# Awareness Diagnose — `/landing awareness <traffic>`

> **Agent:** Teresa (Sales Copywriter) | **Framework:** Schwartz 5 Awareness Levels

## What It Does

Diagnose audience awareness level: unaware, problem, solution, product, most aware.

## Output

Awareness diagnosis with recommended copy framework and traffic temperature
