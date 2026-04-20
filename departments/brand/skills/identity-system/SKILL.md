---
name: brand/identity-system
description: >
  Full brand identity: strategy, verbal, visual in the correct order (never skip to visuals).
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

# Identity System — `/brand identity <name>`

> **Agent:** Valentina (Creative Director) | **Framework:** Wheeler Process + Primal Branding

## What It Does

Full brand identity: strategy, verbal, visual in the correct order (never skip to visuals).

## Output

Complete brand identity package saved to Obsidian

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the website/app and verify brand elements match the identity system (colors, typography, spacing)
- [BROWSER] Compare generated assets side-by-side with the live site
- [BROWSER] Check favicon, og:image, and meta branding elements

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Open design tools (Figma, Canva desktop, Sketch) to verify brand assets match guidelines
