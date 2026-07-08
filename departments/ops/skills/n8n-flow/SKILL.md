---
name: ops/n8n-flow
description: >
  n8n workflow design: AI nodes, webhooks, branching, error handling.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
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
