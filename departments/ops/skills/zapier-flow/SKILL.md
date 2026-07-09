---
name: ops/zapier-flow
description: >
  Designs Zapier workflows: trigger selection, multi-step actions, filters, and error
  notifications, delivered as a Zap spec. TRIGGER: "cria um Zap", "Zapier flow",
  "automatiza com Zapier", "liga estas apps no Zapier", "connect apps with Zapier",
  "/ops zapier <flow>". SKIP: automation platform undecided -> ops/workflow-automate
  (selects Zapier vs Make vs n8n first); AI-heavy or self-hosted flows -> ops/n8n-flow
  (LangChain nodes and self-hosting that Zapier lacks).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Zapier Flow — `/ops zapier <flow>`

> **Agent:** Tomas A. (Automation Engineer) | **Framework:** Zapier Automation Patterns

## What It Does

Zapier workflow design: trigger selection, multi-step actions, error handling.

## Output

Zapier flow spec with trigger, steps, filters, and error notifications
