---
name: content/trend-hunt
description: >
  Demand-first trend and niche analysis — pulls live signal from
  X/Reddit/YouTube/RSS via Agent-Reach (firecrawl/WebSearch fallback),
  scores trends with STEPPS, rates niche viability, and returns top-N
  content angles with hook material. TRIGGER: "/content trends <niche>",
  "que trends há em", "analisa este nicho", "trending topics",
  "what's trending in", "niche analysis", "encontra-me um nicho". SKIP:
  strategic market research for business decisions -> strat department;
  single-video ideation on a known topic -> content/viral-design;
  researching a chosen topic in depth -> content/research-compile.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Trend Hunt — `/content trends <niche>`

> **Agent:** Margarida (Trends & Niche Analyst) | **Frameworks:** Demand-First Content Audit + STEPPS (Berger)

## Backends (multi-backend rule — declare the tier used)

| Tier | Backend | Coverage |
|---|---|---|
| Primary | `agent-reach` CLI | X, Reddit, YouTube transcripts, GitHub, RSS, Exa web search |
| Fallback | `firecrawl_search` + WebSearch | web + news |
| Floor | KB-only | vault notes |

Run `agent-reach doctor --json` first when using the primary; platforms
that fail to pull are SKIPPED AND DECLARED in the report (degraded
mode) — a dead cookie session never blocks the hunt or silently
narrows it.

## Method (demand-first — volume before ideation)

1. **KB pass** — search the vault for prior notes on the niche
   ([[Demand-First Content Audit]], [[Self-Licking Ice Cream Cone
   (Content-Ads Loop)]], previous trend reports); cite hits or declare
   the gap.
2. **Signal sweep** — per platform: what is being discussed, at what
   volume, growing or fading, by whom. Pull competitor transcripts for
   the top-performing pieces (their hooks are data, not inspiration to
   copy).
3. **STEPPS scoring** — score each candidate trend on Social currency /
   Triggers / Emotion / Public / Practical value / Stories (0-3 each,
   max 18). Below 9 → discard.
4. **Niche viability** (when hunting niches, not just topics) — rate
   0-5 each: audience size, competition density (inverted), monetization
   path, fit with the declared target (brand channel, personal brand,
   client vertical, or experimental faceless). Show the matrix.
5. **Angles** — top-N (default 5) content angles: working title, hook
   material (the exact tension/claim/number that earns the click),
   format recommendation (long-form / short / thread), and the evidence
   line behind each.

## Output

Trend report to Obsidian `WizardingCode/Content/Trends/<date>-<niche>.md`:
platform-by-platform signal (with declared skips), STEPPS-scored
shortlist, viability matrix, top-N angles with hooks. Ends with the
handoff line: which angles go to `/content research <topic>` next.

## Examples

```
/content trends "AI agents for solo founders"
/content trends "beleza masculina em Portugal"
/content trends faceless-finance-shorts
```
