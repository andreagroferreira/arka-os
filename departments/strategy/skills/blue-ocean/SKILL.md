---
name: strat/blue-ocean
description: >
  Blue Ocean Strategy analysis: Strategy Canvas to map competition, ERRC Grid
  to find uncontested market space. Based on Kim & Mauborgne.
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

# Blue Ocean Analysis — `/strat blue-ocean <market>`

> **Agent:** Tomas (Chief Strategist) | **Framework:** Blue Ocean Strategy (Kim & Mauborgne)

## Strategy Canvas

Map your offering vs competitors across key factors:

```
HIGH |  *         *
     |  *    *    *    o
     |  *    *    o    o
     |  o    *    o    o    *
LOW  |  o    o              o
     +----+----+----+----+----
      F1   F2   F3   F4   F5

* = Competitor average
o = Your (proposed) offering
```

Factors to map: price, features, ease of use, support, speed, customization, brand, etc.

## ERRC Grid

| Action | Factors | Why |
|--------|---------|-----|
| **Eliminate** | What factors can we eliminate that the industry takes for granted? | Remove cost/complexity |
| **Reduce** | What factors can we reduce well below industry standard? | Cut over-serving |
| **Raise** | What factors can we raise well above industry standard? | Create new value |
| **Create** | What factors can we create that the industry has never offered? | New differentiation |

## Six Paths to Blue Oceans

1. Look across alternative industries
2. Look across strategic groups within the industry
3. Look across the chain of buyers
4. Look across complementary product/service offerings
5. Look across functional vs emotional appeal
6. Look across time (trends)

## Output
- Strategy Canvas diagram (before vs after)
- ERRC Grid with specific factors
- Value innovation statement: what makes this a Blue Ocean
- Risk assessment: can incumbents copy this easily?

## Output → Obsidian: `WizardingCode/Strategy/Blue-Ocean/BLUE-OCEAN-<market>-<date>.md`
