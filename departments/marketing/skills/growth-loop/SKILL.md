---
name: mkt/growth-loop
description: >
  Design sustainable growth loops (viral, paid, product) that compound over time.
  Replaces linear funnels with self-reinforcing cycles.
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

# Growth Loop Design — `/mkt growth-loop`

> **Agent:** Luna (Marketing Director) | **Framework:** Growth Loops (Andrew Chen / Reforge)

## Why Loops > Funnels

Funnels are linear: input stops → output stops.
Loops are circular: output feeds next cycle's input.

## 3 Loop Types

### 1. Viral Loop (User-Generated)
```
User creates content → Content indexed/shared → New user discovers → Signs up → REPEAT
```
Example: Pinterest, YouTube, Notion templates
Key metric: Viral coefficient (K-factor > 1 = exponential)

### 2. Paid Loop (Revenue-Funded)
```
User pays → Revenue reinvested in ads → New user acquired → Pays → REPEAT
```
Example: DTC brands, SaaS with efficient paid
Requirement: LTV:CAC > 3:1, payback < 12 months

### 3. Product Loop (Built-in)
```
User uses product → Product exposes to others → Others join → REPEAT
```
Example: Slack (invite team), Dropbox (share files), Calendly (send invite)
Key metric: Natural rate of growth (organic + viral, no paid)

## Loop Mapping Process

1. **Identify the trigger** — What starts the cycle?
2. **Map the user action** — What does the user do?
3. **Find the output** — What does the action produce?
4. **Trace the reinput** — How does output bring new users?
5. **Measure the cycle** — How long is one loop? What's the conversion at each step?
6. **Optimize the bottleneck** — Which step has the biggest drop-off?

## Output → Growth loop diagram + metrics per step + optimization plan
