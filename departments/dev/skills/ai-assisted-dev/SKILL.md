---
name: dev/ai-assisted-dev
description: >
  AI-assisted development: prompt engineering for code, review AI output, TDD with AI.
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

# Ai Assisted Dev — `/dev ai-dev <task>`

> **Agent:** Paulo (Tech Lead) | **Framework:** AI-Assisted Development Best Practices

## What It Does

AI-assisted development: prompt engineering for code, review AI output, TDD with AI.

## Output

Task completed with AI assistance, all output reviewed and tested
