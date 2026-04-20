---
name: strat/five-forces
description: >
  Porter's Five Forces industry analysis. Evaluates competitive dynamics
  and industry attractiveness.
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

# Five Forces Analysis — `/strat five-forces <industry>`

> **Agent:** Lucas (Market Analyst) | **Framework:** Porter's Five Forces (Michael Porter, 1979)

## The 5 Forces

### 1. Rivalry Among Existing Competitors
- How many competitors? Market concentration?
- Industry growth rate (growing = less rivalry)
- Product differentiation (commodity = high rivalry)
- Switching costs (low = high rivalry)
- Exit barriers (high = firms stay and fight)
**Rating:** Low / Medium / High

### 2. Threat of New Entrants
- Capital requirements to enter
- Economies of scale advantages for incumbents
- Regulatory barriers (licenses, compliance)
- Access to distribution channels
- Brand loyalty and switching costs
**Rating:** Low / Medium / High

### 3. Bargaining Power of Suppliers
- Number of suppliers (few = high power)
- Uniqueness of supplier's product
- Cost of switching suppliers
- Threat of supplier forward integration
**Rating:** Low / Medium / High

### 4. Bargaining Power of Buyers
- Number of buyers (few large = high power)
- Price sensitivity
- Product differentiation (commodity = high buyer power)
- Cost of switching for buyer
- Buyer's access to information
**Rating:** Low / Medium / High

### 5. Threat of Substitutes
- Availability of substitute products/services
- Price-performance of substitutes
- Switching cost to substitute
- Buyer propensity to substitute
**Rating:** Low / Medium / High

## Output Template

```markdown
## Five Forces Analysis: <Industry>

### Industry Attractiveness: [Score: Attractive / Moderate / Unattractive]

| Force | Rating | Key Factor |
|-------|--------|-----------|
| Rivalry | High | 15+ direct competitors, low differentiation |
| New Entrants | Medium | Low capital but strong network effects |
| Supplier Power | Low | Many alternative suppliers |
| Buyer Power | High | Price-sensitive, low switching costs |
| Substitutes | Medium | Some alternatives, moderate switching cost |

### Strategic Implications
1. ...
2. ...
3. ...
```

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Navigate to competitor websites and extract real-time pricing data
- [BROWSER] Capture screenshots of competitor product pages, pricing pages, and feature comparisons
- [BROWSER] Check competitor positioning statements and messaging from their homepage
- [BROWSER] Extract supplier/partner information from competitor sites when available

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Open competitor native apps, screenshot UX patterns, extract feature comparisons

## Scheduling ⏰

```
/schedule weekly — check competitor pricing pages for changes and summarize differences
/schedule monthly — full five forces reassessment for the industry
```

## Output → Obsidian: `WizardingCode/Strategy/Analysis/FIVE-FORCES-<industry>-<date>.md`
