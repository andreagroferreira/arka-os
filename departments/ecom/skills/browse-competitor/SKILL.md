---
name: ecom/browse-competitor
description: >
  Navigates a competitor's e-commerce site with browser integration and
  extracts structured intelligence — product categories, price ranges,
  promotions, layout patterns, payment and shipping info — with screenshots
  into an Obsidian report; falls back to WebFetch when no browser is
  available. TRIGGER: "espia a loja do concorrente", "analisa o site da
  concorrência", "browse competitor store", "vê os preços deles", "/ecom
  browse-competitor <url>". SKIP: strategic competitive landscape without live
  navigation -> marketing/competitor-analysis (research-based positioning, no
  browser needed); auditing YOUR OWN store -> ecom/store-audit (5-agent audit
  of the store you control).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Browse Competitor — `/ecom browse-competitor`

> **Agent:** Ricardo (E-Commerce Director) | Requires: Browser integration (`/chrome`)

## Command

```
/ecom browse-competitor <url>
```

## What It Does

Navigates a competitor's e-commerce site and extracts structured competitive intelligence.

## Workflow

1. **Check browser availability** — follow [Browser Integration Pattern](/arka)
2. **Navigate** to the competitor homepage
3. **Extract** structured data:
   - Product categories and subcategories
   - Price ranges (min, max, average per category)
   - Current promotions and discounts
   - Layout patterns (grid, list, hero sections)
   - Navigation structure
   - Payment methods offered
   - Shipping information
4. **Capture screenshots** of:
   - Homepage
   - A product listing page
   - A product detail page
   - Cart page (if accessible)
   - Footer (payment/shipping badges)
5. **Generate report** in Obsidian with screenshots and structured findings

## Fallback (No Browser)

```
⚠ Browser not available. Using WebFetch for partial extraction.
For full competitor analysis with screenshots, enable: /chrome
```

Falls back to WebFetch/WebSearch for basic HTML extraction (no JS rendering, no screenshots, no interaction).

## Output

Obsidian report: `Projects/<ecosystem>/Strategy/Competitors/<domain>.md`
