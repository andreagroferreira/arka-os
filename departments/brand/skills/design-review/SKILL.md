---
name: brand/design-review
description: >
  Visual review of live designs against brand guidelines and a named
  benchmark — screenshots the real UI (Playwright MCP first, claude-in-chrome
  second, Computer Use for native design tools), and annotates palette,
  typography, spacing, and logo deviations. TRIGGER: "/brand design-review",
  "design review", "visual review", "revê o design", "compara com o
  brandbook", "está on-brand?", "visual QA", "UI review" of mockups or
  screenshots, design file paths (*.fig, *.sketch, Canva links). SKIP:
  reviewing the CODE behind a UI (components, CSS, diffs, PRs) ->
  dev/code-review wins; SOLID/style sweep of frontend code ->
  dev/clean-code-review wins; trying to break flows or find abuse vectors ->
  dev/adversarial-review wins.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Design Review — `/brand design-review`

> **Agent:** Valentina (Creative Director) | **Framework:** Brand fidelity + benchmark comparison
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Command

```
/brand design-review <url-or-app-or-file>
```

Target can be: a running app URL (preferred), Figma, Sketch, Canva, or a
direct design-file path.

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE reviewing, in this order, and record what actually loaded:

1. **`Skill(frontend-design)`** — the reviewer's calibration: the three
   AI-default looks are findings when detected; signature-element
   discipline is the bar.
2. **`Skill(ui-ux-pro-max)`** — palette/typography/guideline data to
   make deviations checkable, not vibes-based.
3. **Read the brand guidelines / design system** — the review compares
   against the project's OWN tokens (`design-system.yaml`, brandbook,
   or §3 of the squad reference as fallback).

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company this design is judged against (from the
`[arka:design]` marker of the work under review when present — hold the
work to ITS declared benchmark; pick and state one when absent).

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE writing the review. Full contract: §9 of the
squad reference.

## Capture order (screenshots are the evidence — no screenshot, no review)

1. **Playwright MCP** (primary, no Computer Use needed):
   `mcp__playwright__browser_navigate` → `browser_take_screenshot` at
   1440 and 390 widths for every reviewed surface.
2. **claude-in-chrome MCP** (second): same capture flow in the user's
   Chrome when Playwright is unavailable.
3. **Computer Use** (last, native design tools only): open Figma /
   Sketch / Canva desktop and screenshot artboards.
4. **Manual fallback**: ask the operator for screenshots — the review
   does not proceed on imagination.

Store captures under `.arka/evidence/ui/<yyyy-mm-dd>/<surface>.png` in
the project — the path the Quality Gate's mechanical `ui-screenshot`
evidence check reads (`core.governance.evidence_checks`): UI-touching
changes with no recent capture (PNG > 10KB, last 24h) fail the evidence
report, and Francisca judges the artifact it points at against the
marker's benchmark.

## Review dimensions

For every captured surface, annotate deviations with exact values
(found vs expected):

- **Palette** — hex fidelity, accent overuse vs the 60/25/15 ratio (§3),
  contrast (AA minimum).
- **Typography** — families, sizes, weights vs the type scale; line
  length and hierarchy integrity.
- **Spacing/layout** — grid conformity, spacing-scale drift (arbitrary
  values are findings), alignment.
- **Logo/iconography** — clear space, min sizes, stroke consistency,
  forbidden treatments.
- **Anti-default (§8)** — does any surface read as one of the three
  AI-default looks? Is there ONE signature element, and is boldness
  spent only there?
- **Benchmark contrast** — for each major finding, one line on what the
  named benchmark does instead.

## Verdict

`ON-BRAND` / `DEVIATIONS (n)` / `OFF-BRAND` — with the annotated
screenshot list, exact-value deviation table, and fix list ranked by
visual impact. A review with zero captured screenshots is INVALID.

## Output

Design review report saved to Obsidian:
`Projects/<ecosystem>/Brand/Reviews/<date>.md`, linking every annotated
capture in `.arka/evidence/ui/<date>/`.
