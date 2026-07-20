---
name: kb/source-evaluate
description: >
  Evaluates a single source's reliability with the CRAAP test — Currency,
  Relevance, Authority, Accuracy, Purpose — producing a scored evaluation with
  a reliability rating. TRIGGER: "avalia esta fonte", "esta fonte é fiável?",
  "evaluate this source", "is this paper credible", "CRAAP test",
  "/kb evaluate <source>". SKIP: a full research effort across multiple
  sources with synthesis -> kb/research-plan (CRAAP is one step of its 5-step
  process); ingesting the source into the vault once it passes ->
  kb/learn-content (ingestion, not evaluation).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Source Evaluate — `/kb evaluate <source>`

> **Agent:** Francisco (Research Analyst) | **Framework:** CRAAP Test

## What It Does

Evaluate source reliability: Currency, Relevance, Authority, Accuracy, Purpose.

## Output

Source evaluation with CRAAP score and reliability rating
