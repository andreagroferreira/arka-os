---
name: brand/ux-audit
description: >
  UX heuristic audit of a live interface against Nielsen's 10 heuristics and
  Laws of UX — navigates real user flows in the browser, checks accessibility
  and responsive breakpoints, and delivers severity-rated findings with fixes.
  TRIGGER: "ux audit", "audita a usabilidade", "auditoria de UX", "heuristic
  evaluation", "porque é que os users se perdem", "/brand ux-audit <url>".
  SKIP: on-brand visual compliance (palette, typography vs brandbook) ->
  brand/design-review; slow pages or Core Web Vitals -> dev/performance-audit;
  brand strength, not interface -> brand/primal-audit.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
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
