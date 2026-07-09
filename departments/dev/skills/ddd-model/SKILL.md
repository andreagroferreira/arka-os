---
name: dev/ddd-model
description: >
  Domain-Driven Design modeling with the Evans/Vernon playbook: bounded
  contexts, aggregates, domain events, context mapping, and ubiquitous
  language — outputs a DDD model with context map and domain event catalog.
  TRIGGER: "DDD", "domain model", "bounded context", "modela o domínio",
  "aggregates", "linguagem ubíqua", "/dev ddd". SKIP: overall system
  architecture and ADRs -> dev/architecture-design (strategic DDD is one
  option there; this goes deeper); persisting the model as tables and
  migrations -> dev/db-schema.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Ddd Model — `/dev ddd <domain>`

> **Agent:** Gabriel (Architect) | **Framework:** DDD (Eric Evans / Vaughn Vernon)

## What It Does

Domain-Driven Design modeling: bounded contexts, aggregates, domain events, context mapping, ubiquitous language.

## Output

DDD model with bounded context map, aggregate definitions, and domain event catalog
