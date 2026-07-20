---
name: org/team-assess
description: >
  Assesses a single team with Team Topologies: topology type, cognitive load,
  skill gaps, and interaction patterns, delivering a topology recommendation
  and improvement actions. TRIGGER: "avalia esta equipa", "a equipa está
  sobrecarregada", "team assessment", "cognitive load da equipa", "skill
  gaps", "/org assess <team>". SKIP: restructuring the whole organization ->
  org/org-design (multi-team redesign); trust, conflict, or accountability
  dysfunction -> lead/team-health (Lencioni Five Dysfunctions).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Team Assess — `/org assess <team>`

> **Agent:** Pedro M. (Org Designer) | **Framework:** Team Topologies + Cognitive Load

## What It Does

Team assessment: topology type, cognitive load, skill gaps, interaction patterns.

## Output

Team assessment report with topology recommendation and improvement actions
