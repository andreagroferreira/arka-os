---
name: pm/story-write
description: >
  Writes user stories with Jeff Patton story mapping and INVEST criteria:
  acceptance criteria, edge cases, test scenarios, and splitting oversized
  stories. TRIGGER: "escreve as user stories", "write user stories", "user
  story para esta feature", "parte esta story", "split this story", "/pm
  story". SKIP: full product-owner cycle (epics, sprints, prioritization)
  -> pm/agile-po (this is the focused single-story flow); ranking existing
  stories -> pm/backlog-groom; formal technical spec with API contracts ->
  dev/spec.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Story Write — `/pm story <description>`

> **Agent:** Sara (Product Owner) | **Framework:** User Story Mapping (Jeff Patton) + INVEST

## What It Does

Write user stories with INVEST criteria, acceptance criteria, and story splitting.

## Output

User story with acceptance criteria, edge cases, and test scenarios
