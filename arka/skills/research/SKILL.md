---
name: arka-research
description: >
  Fan-out research workflow. Spawns 5 parallel subagents — Perplexity,
  Exa AI, Context7, Firecrawl, XMCP — synthesises their findings into
  a single report, and writes a Knowledge Base note to the Obsidian
  vault. Inspired by the multi-source research pattern surfaced in the
  2026-05-13 Orgo podcast (Nick Saraev): "I tell Claude Code, hey,
  spawn five sub-agents — one for Perplexity, one for Exa, one for
  Context7, one for Firecrawl, one for XMCP — and we get best practices."
allowed-tools: [Agent, Read, Write, mcp__obsidian__search_notes]
---

# /arka research — one prompt, five parallel sources

> Companion to `/arka bootstrap-agent`. Where bootstrap-agent generates
> capability, this skill generates *knowledge*.

## Usage

```
/arka research <topic>
```

`<topic>` is a free-form research question. Examples:

- `/arka research "Hermes agent setup with Telegram gateway"`
- `/arka research "Mistral Medium 3.5 cost vs Sonnet 4.6"`
- `/arka research "AIOX Squad de Saúde framework"`

## Sources fanned out

| Subagent | MCP / tool | Strength |
| --- | --- | --- |
| Perplexity | `mcp__perplexity__ask` | Real-time web with citations |
| Exa AI | `mcp__exa__search` | Semantic vector search across the web |
| Context7 | `mcp__context7__query-docs` | Up-to-date official library docs |
| Firecrawl | `mcp__firecrawl__firecrawl_scrape` | Site-specific deep scraping |
| XMCP | `mcp__x__search` | X / Twitter conversations and threads |

If any MCP is not registered in `.mcp.json`, that subagent is skipped
with a `[arka:source-skipped]` note in the report. KB-first protocol
still applies — Obsidian search runs before any external call.

## Workflow

```
1. KB-first: search Obsidian vault for prior notes on the topic.
   If high-confidence matches exist, the report cites them first
   and asks the user whether external research is still needed.

2. Fan out 5 subagents in parallel via the Agent tool. Each gets
   the same topic, returns a focused short brief (≤500 words).

3. Critic synthesis (Tier 0 reviewer, opus): collapses overlap,
   surfaces contradictions, ranks sources by weight (official docs >
   recent community threads > older articles).

4. Synthesis report saved to:
     ${VAULT_PATH}/Knowledge Base/Research/<YYYY-MM-DD>-<slug>.md
   with full citations and a "where to go next" section.

5. Returns a compact summary to the user (the full report links to
   the Obsidian note).
```

## Output shape

```markdown
---
title: <topic>
date: <YYYY-MM-DD>
sources: [perplexity, exa, context7, firecrawl, xmcp]
status: synthesised
tags: [research, <topic-tag>]
---

# <Topic>

## TL;DR
<3-bullet summary>

## Findings by source
### Perplexity
...
### Exa AI
...
(etc.)

## Synthesis
<contradictions resolved, ranked by source weight>

## Next steps
<2-3 follow-up questions or actions>
```

## Cost & budget

This is a heavy operation — 5 parallel LLM calls plus a synthesis call.
A typical run consumes 3-8k tokens. The `/arka costs` skill tracks the
spend and the `[arka:warn]` token-hygiene hook flags excessive use.

## Boundaries

- Read-only: this skill never modifies code or configuration. It only
  writes to the Obsidian Knowledge Base.
- KB-first: always check the vault first. Many topics already have
  notes from prior Dreaming / Research sessions.
- No external research without the user asking — agents do not
  proactively fan out unless `/arka research` is invoked.

## Cross-references

- Source pattern: 2026-05-13 Orgo podcast
- Related: `/arka forge` (planning, not research)
- Related: `/kb research` (Clara, knowledge management)
- Related: `/arka bootstrap-agent` (capability-from-research)
