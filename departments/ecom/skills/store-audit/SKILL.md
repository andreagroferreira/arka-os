---
name: ecom/store-audit
description: >
  Full store audit: UX, SEO, performance, content, conversion with 5 parallel agents.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

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
