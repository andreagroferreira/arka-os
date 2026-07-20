---
name: kb/ai-research
description: >
  AI-augmented research: uses Perplexity, Elicit, and Claude for source gathering
  and synthesis, delivering a research report with CRAAP-rated sources and
  synthesized findings. TRIGGER: "pesquisa com AI", "usa o Perplexity para
  investigar", "AI research on this topic", "gather sources with AI tools",
  "/kb ai-research <topic>". SKIP: full research methodology from question
  definition to synthesis -> kb/research-plan (owns the 5-step process; this
  skill is its AI-tooling arm); digging into a named competitor ->
  kb/competitive-intel (structured competitor profile, not open research).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Ai Research — `/kb ai-research <topic>`

> **Agent:** Francisco (Research Analyst) | **Framework:** AI-Augmented Research Workflow

## What It Does

AI-augmented research: use Perplexity, Elicit, Claude for source gathering and synthesis.

## Output

Research report with AI-gathered sources, CRAAP-rated, synthesized findings
