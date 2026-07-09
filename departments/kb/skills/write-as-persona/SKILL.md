---
name: kb/write-as-persona
description: >
  Writes content in a learned persona's voice, applying their frameworks,
  style, and KB knowledge, with framework references in the output. TRIGGER:
  "escreve como o X", "escreve na voz da persona", "write as <persona> about
  X", "draft this in her style", "/kb write <persona> <topic>". SKIP: the
  persona does not exist yet or needs refinement -> kb/persona-build (build
  the advisor first); generic content without a persona voice ->
  content/hook-write or the /content department skills (regular copy, not
  persona mimicry).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Write As Persona — `/kb write <persona> <topic>`

> **Agent:** Clara (Knowledge Director) | **Framework:** Persona Voice + KB Knowledge

## What It Does

Write content in a learned persona's voice using their frameworks and style.

## Output

Content written in persona voice with framework references
