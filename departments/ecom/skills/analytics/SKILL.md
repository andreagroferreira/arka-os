---
name: ecom/analytics
description: >
  E-commerce metrics analysis — AOV, conversion rate, CLV, ROAS, and cart
  abandonment — delivered as a dashboard with funnel visualization and
  benchmark comparison, plus browser verification that GA4, Meta Pixel, and
  GTM tracking fire correctly. TRIGGER: "métricas da loja", "qual é o AOV",
  "store analytics", "conversion rate da loja", "verifica o tracking GA4",
  "/ecom analytics". SKIP: cross-channel campaign reporting ->
  marketing/analytics-report (campaign-level, not store-level metrics);
  diagnosing WHY conversion is low and building a test backlog
  -> ecom/cro-optimize (research-driven optimization, not measurement).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
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
