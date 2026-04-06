---
name: ops/dashboard-build
description: >
  Operational dashboard design: select metrics, define targets, build layout.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Dashboard Build — `/ops dashboard <area>`

> **Agent:** Daniel (Ops Lead) | **Framework:** Lean Analytics (Croll) + OMTM

## What It Does

Operational dashboard design: select metrics, define targets, build layout.

## Output

Dashboard spec with metrics, targets, data sources, and alert thresholds

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the dashboard in browser and verify all widgets render correctly
- [BROWSER] Check that data loads and updates in real-time (if WebSocket)
- [BROWSER] Test responsive layout at different screen sizes
- [BROWSER] Verify charts, tables, and graphs display correct data

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Launch dashboard app and verify widgets, charts, and real-time data render correctly

## Scheduling ⏰

```
/loop 10m check dashboard API health and flag if any endpoint returns errors
/schedule hourly — verify dashboard data freshness and alert if stale
```
