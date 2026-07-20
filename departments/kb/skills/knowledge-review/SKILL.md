---
name: kb/knowledge-review
description: >
  Knowledge freshness review of the Obsidian vault: identifies stale notes,
  updates progressive summaries, and fixes broken links, producing a review
  report with actions taken. TRIGGER: "revê a base de conhecimento", "notas
  desatualizadas", "review the vault", "fix broken links in the KB", "/kb review".
  SKIP: reorganising tags, categories, or naming -> kb/taxonomy-manage
  (structure, not freshness); building an index page for a grown topic
  cluster -> kb/moc-create (creates MOCs rather than auditing note health).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Knowledge Review — `/kb review`

> **Agent:** Helena C. (Knowledge Curator) | **Framework:** Progressive Summarization + Review Cycle

## What It Does

Knowledge freshness review: identify stale notes, update summaries, fix broken links.

## Output

Review report with stale notes identified and actions taken
