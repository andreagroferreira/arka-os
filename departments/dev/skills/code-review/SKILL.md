---
name: dev/code-review
description: >
  Code review against Clean Code and SOLID. Checks naming, SRP, DIP, test coverage, security.
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
