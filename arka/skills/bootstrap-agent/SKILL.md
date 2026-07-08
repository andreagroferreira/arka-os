---
name: arka-bootstrap-agent
description: >
  Formalises the "agents set up agents" pattern surfaced in the 2026-05-13
  Nick Saraev × Greg Isenberg podcast on the Orgo agent business. When the
  user asks to spin up a new specialist or an integration that requires
  research-heavy setup, this skill orchestrates The Forge to dispatch
  research subagents (Perplexity / Exa / Context7 / Firecrawl / XMCP),
  synthesises the findings, and produces a ready-to-use agent YAML or
  installation guide.
allowed-tools: [Agent, Read, Write, Bash]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# /arka bootstrap-agent — agents that set up agents

> Pattern source: Nick Saraev (Orgo) interview, 2026-05-13. ArkaOS already
> has The Forge for complexity-based planning; this skill is the explicit
> entry point users invoke when they want a new specialist or a setup
> playbook rather than a feature.

## Subcommands

| Command | What it does |
| --- | --- |
| `/arka bootstrap-agent specialist <slug>` | Generates a new Tier 2 agent YAML for a domain you describe. Dispatches research subagents to gather domain frameworks, conventions, and common pitfalls. Produces `departments/<dept>/agents/<slug>.yaml` with full 4-framework DNA. |
| `/arka bootstrap-agent integration <tool>` | Installation playbook for an external tool (e.g. Hermes, Composio, Agent Mail). Researches official docs + community recipes, outputs a step-by-step setup guide and any required MCP config. |
| `/arka bootstrap-agent persona <name>` | Builds an AI persona profile (DISC + Enneagram + OCEAN + MBTI) from learned content. Delegates to `/kb` (Clara) for source ingestion. |

## How it works

```
User: /arka bootstrap-agent specialist "design-tokens-engineer"
  │
  ▼
1. The Forge classifies request complexity (usually "medium" — single
   specialist, multiple research dimensions).
2. Spawns 3-5 research subagents in parallel:
     - Perplexity MCP → real-time framework discovery
     - Exa AI → semantic search for prior art
     - Context7 → official documentation pulls
     - Firecrawl → scrape competitor / canonical sources
     - XMCP → Twitter / X conversations for community wisdom
3. Critic synthesis: a Tier 0 reviewer collapses overlap, surfaces
   contradictions, prioritises by source weight.
4. Generates the deliverable (YAML / playbook / persona) and saves to
   the canonical path.
5. Quality Gate (Marta + Eduardo + Francisca) approves before output
   reaches the user.
```

## Why this exists

Per the Orgo interview, the recurring pattern in successful one-person
agent businesses is "use agents to set up agents". ArkaOS already had
the primitives — The Forge for planning, the Agent tool for subagent
dispatch, KB-first research — but no single entry point that made the
pattern *the* way to add capability. This skill is that entry.

## Boundaries

- This skill **generates**. It does not modify production code.
- The generated YAML lands in `departments/<dept>/agents/` for review;
  it is **not** auto-registered until the user commits and the next
  loader pass picks it up.
- Personas built via this skill go through `/kb` for the actual
  content ingestion (YouTube / PDFs / articles). This skill orchestrates,
  it does not bypass the knowledge pipeline.

## Cross-references

- Source pattern: 2026-05-13 Orgo podcast (Nick Saraev × Greg Isenberg)
- Related: `/arka forge` (planning engine, lower level)
- Related: `/kb persona` (content-driven persona builder)
- Related: `/arka research` (the same research-fan-out pattern for
  one-off knowledge tasks rather than agent generation)
- Memory: [[project_next_level_conclave]]
