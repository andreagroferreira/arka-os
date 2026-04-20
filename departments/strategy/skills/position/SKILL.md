---
name: strat/position
description: >
  Competitive positioning: alternatives, unique capabilities, value, target, category.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Position — `/strat position <product>`

> **Agent:** Tomas (Chief Strategist) | **Framework:** Positioning (Ries/Trout) + April Dunford

## What It Does

Competitive positioning: alternatives, unique capabilities, value, target, category.

## Output

Positioning statement + perceptual map + competitive differentiation

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Visit competitor websites and extract their positioning: taglines, hero copy, value propositions
- [BROWSER] Capture visual identity elements: color schemes, typography, imagery style
- [BROWSER] Check social proof: testimonials, client logos, case studies
- [BROWSER] Compare pricing pages side-by-side

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Launch competitor apps side-by-side, compare UI/UX, capture positioning differences

## Scheduling ⏰

```
/schedule monthly — review competitor positioning changes: taglines, messaging, pricing
/schedule quarterly — full competitive positioning reassessment
```
