---
name: ecom/store-audit
description: >
  Full store audit with 5 parallel agents — UX, SEO, performance, content, and
  conversion — including live browser checks of the checkout flow, mobile
  responsiveness, and page speed, delivering a scored report with prioritized
  fixes. TRIGGER: "audita a minha loja", "store audit", "analisa a loja
  completa", "health check da loja", "/ecom audit <url>". SKIP: deep
  conversion research with an A/B test backlog -> ecom/cro-optimize
  (ResearchXL goes deeper than the audit's conversion pass); auditing a
  competitor's store -> ecom/browse-competitor (their store, not yours); SEO-
  only pass -> marketing/seo-audit.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Store Audit — `/ecom audit`

> **Agent:** Ricardo (E-Commerce Director) | **Framework:** 5-Agent Parallel Audit

## What It Does

Full store audit: UX, SEO, performance, content, conversion with 5 parallel agents.

## Output

Comprehensive audit report with scores per area and prioritized fixes

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open store URL and test the full checkout flow: browse → add to cart → checkout → payment → confirmation
- [BROWSER] Test mobile responsiveness at different viewport sizes (375px, 768px, 1024px)
- [BROWSER] Capture screenshots of homepage, product page, cart, and checkout for the audit report
- [BROWSER] Check page load performance via console timing (Performance API)
- [BROWSER] Verify search functionality works correctly
- [BROWSER] Test navigation menu and footer links

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] If mobile app: open in iOS Simulator, test purchase flow, verify responsiveness

## Scheduling ⏰

```
/schedule daily at 8am — quick store health check: uptime, broken links, price errors
/loop 1h check store homepage and top 5 product pages for errors or downtime
```
