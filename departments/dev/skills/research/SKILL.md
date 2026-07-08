---
name: dev/research
description: >
  Dev-scoped technical research (Lucas, Analyst): library evaluation,
  framework/package selection, code pattern comparison, and engineering
  best-practice discovery via Context7 official docs + web research,
  ending in a trade-off report with a recommendation.
  TRIGGER: user types "/dev research", "avalia a biblioteca", "que
  lib/framework usamos", "compara X vs Y" for code dependencies,
  "library evaluation", "which package/ORM/framework should we use",
  "best practice" questions about implementation choices — load BEFORE
  adding a new dependency or committing to an architecture-relevant
  library.
  SKIP: general, market, or knowledge-base research whose deliverable
  is an Obsidian KB note — arka-research (/arka research, 5-source
  fan-out) wins; requirements definition — arka-dev-spec wins.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Research — `/dev research <topic>`

> **Agent:** Lucas (Analyst) | **Framework:** Context7 + Web Research

## What It Does

Research a technical topic: library evaluation, pattern comparison, best practice discovery.

## Output

Research report with options, trade-offs, and recommendation
