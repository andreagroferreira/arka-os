---
name: dev/code-review
description: >
  General code review of a file, diff, or PR against Clean Code, SOLID, test
  coverage, and baseline security — the default pre-merge review pass in dev
  workflows. TRIGGER: "/dev review", "code review", "review this PR/diff/file",
  "revê o código", "faz review", "revê este PR", "análise ao código",
  "pode fazer merge?"; run BEFORE approving any merge. SKIP: pure
  naming/SOLID/style sweep with no test, security, or merge concern ->
  dev/clean-code-review wins; red-team pass, "try to break it", hostile edge-case
  or abuse-vector hunting -> dev/adversarial-review wins; visual/UI/brand review
  (Figma, screenshots, pixels, guidelines) -> brand/design-review wins.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Code Review — `/dev review <file/pr>`

> **Agent:** Paulo (Tech Lead) | **Framework:** Clean Code + SOLID (Uncle Bob)

## What It Does

Code review against Clean Code and SOLID. Checks naming, SRP, DIP, test coverage, security.

## Output

Review report: BLOCKER/WARNING/NOTE with line references and fix suggestions

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the application in the browser and verify UI changes visually
- [BROWSER] Check browser console for JavaScript errors or warnings
- [BROWSER] If CSS/layout changes: compare before/after visually

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] If native app: launch and click through UI to verify changes visually

## Scheduling ⏰

```
/loop 30m check open PRs on this repo and summarize any that need review
/schedule weekdays at 9am — review all open PRs and post summary
```
