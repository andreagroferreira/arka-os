---
name: brand/primal-audit
description: >
  Audit an existing brand against Patrick Hanlon's 7 Primal Code elements.
  Identifies missing elements and provides recommendations to strengthen the brand.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
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

# Primal Brand Audit — `/brand audit`

> **Agent:** Mateus (Brand Strategist) | **Framework:** Primal Branding (Patrick Hanlon)

## The 7 Primal Code Elements

| # | Element | Question | Status |
|---|---------|----------|--------|
| 1 | **Creation Story** | How was the brand born? Is it told consistently? | |
| 2 | **Creed** | What does the brand believe? Core principles? | |
| 3 | **Icons** | What visual symbols are instantly associated? | |
| 4 | **Rituals** | What repeated interactions define the experience? | |
| 5 | **Non-Adherents** | Who is the opposition? What are we NOT? | |
| 6 | **Sacred Lexicon** | What special language do believers use? | |
| 7 | **Leader** | Who embodies the brand values? Visible face? | |

## Audit Process

1. **Gather** — Collect all brand assets: website, social, packaging, internal docs
2. **Map** — Fill each of the 7 elements with what currently exists
3. **Score** — Rate each element: Strong (3), Present (2), Weak (1), Missing (0)
4. **Gaps** — Identify missing or weak elements
5. **Recommend** — Specific actions to strengthen each weak element
6. **Benchmark** — Compare against competitors' Primal Codes

## Scoring

| Score | Rating | Meaning |
|-------|--------|---------|
| 18-21 | Iconic | Brand has cult-like following potential |
| 14-17 | Strong | Well-defined, minor gaps to fill |
| 10-13 | Developing | Foundation exists, significant gaps |
| 0-9 | Underdeveloped | Major brand building needed |

## Output → Obsidian: `WizardingCode/Brand/Audits/PRIMAL-AUDIT-<brand>-<date>.md`
