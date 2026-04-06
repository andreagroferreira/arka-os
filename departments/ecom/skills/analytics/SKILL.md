---
name: ecom/analytics
description: >
  E-commerce analytics: AOV, conversion rate, CLV, ROAS, cart abandonment rate.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

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
