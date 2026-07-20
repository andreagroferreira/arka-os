---
name: dev/ai-assisted-dev
description: >
  AI-assisted development practice: prompt engineering for code generation,
  structured review of AI output, and TDD with AI in the loop. TRIGGER: "ai
  dev", "prompt engineering", "gera código com IA", "review AI output",
  "programar com IA", "code with AI", "/dev ai-dev". SKIP: securing AI/LLM
  systems (prompt injection, guardrails) -> dev/ai-security (assessment, not
  development practice); building MCP servers -> dev/mcp-builder; plain TDD
  without AI in the loop -> dev/tdd-cycle.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Ai Assisted Dev — `/dev ai-dev <task>`

> **Agent:** Paulo (Tech Lead) | **Framework:** AI-Assisted Development Best Practices

## What It Does

AI-assisted development: prompt engineering for code, review AI output, TDD with AI.

## Output

Task completed with AI assistance, all output reviewed and tested
