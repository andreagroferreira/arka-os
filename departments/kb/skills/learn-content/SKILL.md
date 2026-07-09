---
name: kb/learn-content
description: >
  Ingests a content source (YouTube video, article, PDF): downloads, transcribes,
  and analyzes it with 5 parallel agents, storing frameworks, insights, and
  cross-references in Obsidian. TRIGGER: "aprende com este vídeo", "ingere este
  artigo", "learn from this URL", "transcribe and analyze this podcast",
  "/kb learn <url>". SKIP: managing the ingestion QUEUE, KB search, or a
  multi-source persona build -> kb/knowledge (the department umbrella; this
  skill handles ONE source end-to-end); turning raw notes into atomic
  permanent notes -> kb/zettelkasten-process (note workflow, not source
  ingestion); building a callable advisor from already-ingested content ->
  kb/persona-build; investigating an open question -> kb/research-plan
  (research, not ingestion).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Learn Content — `/kb learn <url>`

> **Agent:** Clara (Knowledge Director) | **Framework:** 5-Agent Parallel Analysis

## What It Does

Ingest content (YouTube, article, PDF): download, transcribe, analyze with 5 agents.

## Output

Processed content in Obsidian with frameworks, insights, and cross-references
