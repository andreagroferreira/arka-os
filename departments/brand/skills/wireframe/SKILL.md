---
name: brand/wireframe
description: >
  Designs wireframes — layout, navigation, content hierarchy, and interaction
  notes — using Garrett's 5 Planes and information architecture, delivered as
  an annotated spec with component references and responsive notes. TRIGGER:
  "wireframe", "esboça a página", "estrutura da página", "low-fi layout",
  "wireframe the dashboard", "/brand wireframe <page>". SKIP: full
  landing-page conversion structure -> landing/page-architect
  (conversion-driven section architecture); pixel-level brand-applied visuals
  -> brand/mockup-generate (wireframes come first).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Wireframe — `/brand wireframe <page>`

> **Agent:** Sofia D. (UX Designer) | **Framework:** Garrett's 5 Planes + Information Architecture
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE sketching a single box, in this order, and record what
actually loaded:

1. **`Skill(frontend-design)`** — anti-default doctrine: layout concepts
   are compared as one-sentence prose + ASCII wireframes BEFORE choosing;
   structure is information, not decoration.
2. **`Skill(ui-ux-pro-max)`** — 99 UX guidelines and per-product-type
   interface patterns; use them to pressure-test the information
   architecture, not to pick a template.
3. **Read the project design system** — grid, spacing scale, breakpoints
   (`design-system.yaml` or §3 of the squad reference as fallback).

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company whose information density and hierarchy this
page should be judged against (Linear for ruthless density, Stripe for
progressive disclosure, Notion for flexible blocks…), and state what
that company's design lead would reject in your current structure.

## Anti-default check

The wireframe stage is where the broadsheet default (§8) sneaks in —
numbered markers (01/02/03), hero-with-big-number-and-gradient, dense
hairline columns. Use a structural device ONLY if it encodes something
true about the content (a real sequence, a real timeline). Self-test:
*"would this exact structure appear for any other brief?"*

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE the first Write/Edit. Full contract: §9 of
the squad reference.

## Workflow (Garrett's 5 Planes, applied)

1. **Strategy** — one sentence: the page's single job and its audience.
   If the brief doesn't pin these, pin them yourself and say so.
2. **Scope** — content inventory: every element that must exist, ranked
   by the user's need (not the org chart's pride).
3. **Structure** — user flows in/out of the page; navigation model;
   where each ranked element lives. State the ONE thing a first-time
   visitor must understand in 5 seconds.
4. **Skeleton** — ASCII wireframes at TWO breakpoints minimum (desktop
   ~1440, mobile ~390), exploring at least TWO structurally different
   layout concepts with a one-sentence rationale each; pick one and say
   why the loser lost.
5. **Surface handoff** — annotate: interaction notes (hover, focus,
   empty, error, loading states), component references (map every region
   to a design-system component or flag it as NEW), responsive behavior
   per region, and the intended signature element's location.

## Output

An annotated wireframe spec:

| Section | Content |
|---|---|
| Strategy line | page job + audience + 5-second takeaway |
| Content inventory | ranked element list |
| ASCII wireframes | ≥2 concepts × 2 breakpoints, winner + rationale |
| Annotations | interaction states, component refs, responsive notes |
| Signature | where the one memorable element lives and why |

Saved to Obsidian under the project's Brand/UX path; consumed by
`brand/mockup-generate` and `dev` implementation with the marker's
`tokens=` pointing at the same design system.
