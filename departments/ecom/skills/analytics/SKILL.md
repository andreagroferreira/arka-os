---
name: ecom/analytics
description: >
  E-commerce analytics: AOV, conversion rate, CLV, ROAS, cart abandonment rate.
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

# Analytics — `/ecom analytics`

> **Agent:** Alice (CRO Specialist) | **Framework:** E-Commerce Metrics Stack

## What It Does

E-commerce analytics: AOV, conversion rate, CLV, ROAS, cart abandonment rate.

## Output

Analytics dashboard with funnel visualization and benchmark comparison

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the store and verify GA4 tracking fires on page load (check Network tab for collect requests)
- [BROWSER] Test conversion tracking: complete a purchase flow and verify events fire
- [BROWSER] Check Meta Pixel fires correctly (search for fbq in console)
- [BROWSER] Verify Google Tag Manager container loads

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Open analytics dashboards in native apps (Mixpanel, Amplitude) and verify event tracking

## Scheduling ⏰

```
/loop 1h check store conversion rate and flag if below 2% threshold
/schedule daily at 9am — morning e-commerce metrics summary: revenue, orders, conversion, AOV
```
