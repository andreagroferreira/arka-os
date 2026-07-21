---
name: colors
description: >
  Designs a brand color palette — primary, secondary, accent, and neutrals —
  delivered with hex codes, usage guidelines, and WCAG contrast checks.
  TRIGGER: "paleta de cores", "escolhe as cores da marca", "color palette",
  "brand colors", "que cores combinam com esta marca", "/brand colors <mood>".
  SKIP: palette as part of a full token and component system ->
  brand/design-system (tokens, atomic catalog, WCAG gates for the whole UI);
  complete brand identity from strategy up -> brand/identity-system.
metadata:
  origin: community
  source: https://github.com/nutlope/hallmark
  license: MIT
---

# Colors

> **Agent:** Isabel (Visual Designer) | **Framework:** Color Theory + Accessibility
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE proposing a single hex value, in this order, and record
what actually loaded:

1. **`Skill(frontend-design)`** — Anthropic's anti-default doctrine: the
   three AI-default looks, token-plan-then-critique, signature discipline.
2. **`Skill(ui-ux-pro-max)`** — curated design data: 161 palettes,
   57 font pairings, 99 UX guidelines; use its palette data as
   comparative evidence, never as a menu to copy from.
3. **Read the project design system** — `design-system.yaml`, token
   files, or the brandbook; §3 of the squad reference is the in-repo
   fallback when the Obsidian note is unreachable.

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company (Linear, Stripe, Vercel, Notion, Airbnb…)
whose color craft this brand should be judged against, and write one
line on what that company's design lead would reject in your current
direction. No named benchmark, no palette.

## Anti-default check

Before finalizing: which of the three AI-default looks (§8 — cream +
serif + terracotta; dark + acid accent; broadsheet) is this palette
drifting toward? Self-test: *"would this exact palette appear for any
other brief?"* If yes, revise and state what changed and why.

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE the first Write/Edit. Full contract: §9 of
the squad reference.

## Workflow

1. **KB + brief** — search the vault for existing brand/palette notes;
   extract the mood words from the brief and the subject's own world
   (its materials, environments, vernacular — that is where
   non-default color comes from).
2. **Anchor** — pick the anchor hue from the subject, not from fashion.
   State the reasoning in one sentence.
3. **Build the palette as 4–6 NAMED roles** (name = function, never
   "blue"): `surface` (canvas), `ink` (text), `primary` (identity),
   `accent` (signal, ≤ 10–15% usage), plus optional `positive`/`danger`
   semantics. Derive tints/shades in OKLCH so lightness steps are
   perceptually even; give each role a hex. **The full construction
   algorithm lives in `references/oklch-theme.md`** (anchor → paper →
   ink → greys → focus → accent-ink, with L/C bands per vibe, tinted
   neutrals, dark-mode-is-not-inverted-light, and three worked
   examples) — follow it, don't improvise the steps.
4. **WCAG pairs table** — for every text-bearing combination, compute
   the contrast ratio and mark AA/AAA for body and large text. Any pair
   below AA is redesigned, not footnoted.
5. **Dark-mode variants** — restate every role for dark surfaces (do
   not naive-invert; re-pick lightness in OKLCH).
6. **Usage guidelines** — the 60/25/15 composition ratio (§3), do/don't
   examples, and which role carries the signature element.
7. **Critique pass** — rerun the anti-default self-test against the
   named benchmark before delivering.

## Output

A palette block ready for token systems (DTCG-shaped: role → hex +
OKLCH), the WCAG pairs table, dark-mode variants, and usage guidelines
— saved to Obsidian under the project's Brand path and referenced by
`tokens=` in the design marker of any implementation that follows.

| Deliverable | Format |
|---|---|
| Palette (4–6 named roles) | hex + OKLCH per role, light + dark |
| Contrast evidence | WCAG pairs table (AA/AAA per combination) |
| Usage guide | 60/25/15 ratio, do/don't, signature carrier |
