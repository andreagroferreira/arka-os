---
name: brand/ux-audit
description: >
  UX heuristic audit: evaluate interface against Nielsen's 10 heuristics.
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

# Ux Audit — `/brand ux-audit <url>`

> **Agent:** Sofia D. (UX Designer) | **Framework:** Nielsen 10 Heuristics + Laws of UX

## What It Does

UX heuristic audit: evaluate interface against Nielsen's 10 heuristics.

## Output

Heuristic audit report with severity ratings and fix recommendations

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Navigate the site following primary user flows (onboarding, core action, checkout)
- [BROWSER] Test accessibility: tab navigation, focus indicators, color contrast
- [BROWSER] Capture screenshots of key screens for the UX audit report
- [BROWSER] Check responsive design at mobile, tablet, and desktop breakpoints
- [BROWSER] Verify loading states, error states, and empty states render correctly

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Launch the native app, test user flows, screenshot each screen for the audit report

## Scheduling ⏰

```
/schedule weekly — run Lighthouse audit on main pages, flag performance regressions
/schedule monthly — full UX heuristic review of core user flows
```
