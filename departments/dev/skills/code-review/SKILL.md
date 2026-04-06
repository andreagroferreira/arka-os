---
name: dev/code-review
description: >
  Code review against Clean Code and SOLID. Checks naming, SRP, DIP, test coverage, security.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

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
