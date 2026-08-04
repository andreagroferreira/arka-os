---
name: brand/design-dna
description: >
  Extracts the design DNA of a reference UI into a structured JSON profile
  across three dimensions — design_system (measurable tokens), design_style
  (qualitative feel), visual_effects (WebGL, shaders, particles, scroll) —
  and generates new UI from that profile. Works from screenshots, images, or
  live URLs.
  TRIGGER: "design DNA", "extrai o DNA", "replica este estilo", "faz igual a
  este site", "clone this aesthetic", "design tokens from reference", "style
  guide JSON", "analisa este design", "gera a partir deste DNA", "/brand
  design-dna"; any request that supplies a reference artefact (screenshot,
  image, URL) and asks for the look to be reproduced.
  SKIP: building a design system from scratch with no reference artefact ->
  brand/design-system (it specifies a system; this one reverse-engineers
  one); only a colour palette -> brand/colors; judging an existing UI against
  brand guidelines -> brand/design-review; the full identity package
  (strategy, verbal, visual) -> brand/identity-system.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch]
metadata:
  origin: community
  source: https://github.com/zanwei/design-dna
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Design DNA — `/brand design-dna`

> **Agent:** Valentina (Creative Director) with Nia (extraction) and Iris (tokens)
> **Framework:** 3-dimension DNA schema (design_system / design_style / visual_effects)

## What It Does

Turns a reference UI into a machine-readable profile, then builds new
interfaces from it. Three phases, invoked in any combination.

## The three dimensions

Design systems usually capture only the first of these. The other two are
why a faithful token dump still fails to look like the reference.

| Dimension | What it holds | How it is captured |
|---|---|---|
| `design_system` | colour, typography, spacing, layout, shape, elevation, iconography, motion, components | measured — hex values, rem scales, pixel radii |
| `design_style` | aesthetic, visual language, composition, imagery, interaction feel, brand voice in UI | judged — mood, personality, ornamentation, whitespace philosophy |
| `visual_effects` | background effects, particles, 3D, shaders, scroll (parallax, triggers, morphing), text and cursor effects, glassmorphism | observed — what cannot be expressed in CSS alone |

Full field list: [references/schema.md](references/schema.md).

## Phase 1 — Structure

Present the schema and its three dimensions, then ask whether any dimension
should be extended or dropped for this project.

## Phase 2 — Analyse

For each reference supplied (image, screenshot, or URL), populate every
schema field. Where references conflict, name the dominant pattern and note
the variants rather than averaging them into mush.

**Delegate the measurable work to Nia** (`extraction-script-writer`): computed
styles, palette reverse-engineering from live DOM or screenshot, typography
harvesting. Nia returns numbers; this skill turns them into the profile. For
a live URL, real extraction beats estimation every time — do not eyeball what
a script can read.

The doctrine for reading a page's design lives in
`brand/design-system/references/design-dna-study.md`. Read it before judging
a reference: it is the observational method, this skill is the workflow that
consumes it.

For `visual_effects`, scan the source for `<canvas>`, WebGL contexts,
Three.js or Pixi imports, GSAP and Lottie usage, custom shaders, and
scroll-driven observers. When the implementation cannot be determined from
what is available, describe the effect in `composite_notes` and say so —
an honest gap beats an invented technique.

## Phase 3 — Generate

Build CSS custom properties from `design_system`, let `design_style` drive
the subjective calls, and implement `visual_effects` at the right weight.
Fetch real assets from the source URL when one was given; do not approximate
an asset you can download.

Effect weight decides the technique, and the profile should name the tier
so whoever builds it does not over-engineer a hover state or under-build a
hero:

| Tier | Technique | Cost to watch |
|---|---|---|
| Light | CSS animation, SVG, vanilla JS | none worth measuring |
| Medium | scroll-driven and timeline animation, Canvas 2D, Lottie | main-thread work during scroll |
| Heavy | real-time 3D, GLSL shaders, particle systems | GPU budget, first paint, battery on mobile |

Record the tier in `visual_effects.overview.performance_tier` and hand the
build to the frontend squad — this skill decides WHAT the effect is and how
strong, not how to code it.

Run the quality checks in
[references/generation-guide.md](references/generation-guide.md) before
delivering.

## Output

A complete Design DNA JSON with every field populated, plus — when Phase 3
runs — the generated interface and the token file it was built from. Both to
the Obsidian vault under the project's brand folder.
