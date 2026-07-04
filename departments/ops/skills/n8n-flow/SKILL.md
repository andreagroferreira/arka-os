---
name: ops/n8n-flow
description: >
  n8n workflow design: AI nodes, webhooks, branching, error handling.
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

# N8N Flow — `/ops n8n <flow>`

> **Agent:** Tomas A. (Automation Engineer) | **Framework:** n8n AI-Native Workflows

## What It Does

n8n workflow design: AI nodes, webhooks, branching, error handling.

## Event-driven watching (Monitor)

When validating a deployed flow, prefer the runtime's Monitor tool over
polling loops — zero idle tokens versus a model turn per interval.

```
Monitor: watch the n8n execution log (or webhook endpoint output) until
/error|failed|succeeded/ matches, then inspect that execution and report.
```

Fallback: on runtimes without Monitor, use a wide-interval `/loop` and
stop it as soon as the first relevant event lands.

## Output

n8n flow spec with node configuration and AI integration points
