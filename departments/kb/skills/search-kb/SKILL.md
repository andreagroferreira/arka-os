---
name: kb/search-kb
description: >
  Searches the Obsidian knowledge base: keyword, semantic, and cross-reference
  search across the vault, returning relevance-ranked results with related
  notes. TRIGGER: "pesquisa na base de conhecimento", "procura no vault",
  "search the KB for X", "what do we know about X", "/kb search <query>".
  SKIP: gathering NEW external information the vault lacks -> kb/research-plan
  (external research, not retrieval); reviewing or fixing stale notes that
  search surfaces -> kb/knowledge-review (maintenance, not lookup).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Search Kb — `/kb search <query>`

> **Agent:** Clara (Knowledge Director) | **Framework:** Semantic Search + Obsidian

## What It Does

Search the knowledge base: keyword, semantic, cross-reference across vault.

## Output

Search results with relevance ranking and related notes
