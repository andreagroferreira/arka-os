---
name: dev/db-design
description: >
  Database design with the DBA (Vasco): schema modeling, normalization, index
  strategy, RLS policies, and migration planning — outputs ERD, migration
  scripts, and policy definitions. TRIGGER: "database design", "desenha a base
  de dados", "modelo de dados", "indexes", "RLS", "planeia as migrações",
  "/dev db"; load BEFORE writing migrations. SKIP: feature-level schema with
  Laravel migration code and cross-cutting concerns -> dev/db-schema (feature
  scope; this is DB-wide design); slow-query diagnosis ->
  dev/performance-audit.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Db Design — `/dev db <action>`

> **Agent:** Vasco (DBA) | **Framework:** Normalization + Indexing Best Practices

## What It Does

Database design: schema, normalization, indexes, RLS policies, migration planning.

## Output

ERD diagram, migration scripts, index strategy, RLS policy definitions
