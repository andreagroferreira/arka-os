---
name: kb/moc-create
description: >
  Creates or updates a Map of Content (LYT, Nick Milo) when a topic cluster
  reaches 10+ notes, producing an Obsidian MOC page with linked notes organized
  by subtopic. TRIGGER: "cria um MOC", "organiza este cluster de notas",
  "map of content for X", "index this topic", "/kb moc <cluster>". SKIP:
  renaming tags or restructuring categories vault-wide -> kb/taxonomy-manage
  (taxonomy hierarchy, not topic index pages); auditing note freshness and
  broken links -> kb/knowledge-review (health check, not organization).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Moc Create — `/kb moc <cluster>`

> **Agent:** Helena C. (Knowledge Curator) | **Framework:** LYT / Maps of Content (Nick Milo)

## What It Does

Create or update a Map of Content when a topic cluster reaches 10+ notes.

## Output

MOC page in Obsidian with linked notes organized by subtopic
