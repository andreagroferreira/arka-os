# Layout Craft — space, rhythm, responsive floors

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT) and [impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0) — see `hallmark.LICENSE` and `impeccable.LICENSE` in this references directory.

Layout is where "AI-generated" gets caught. Equal columns, everything centred, every card identical — these are the tells. Space is the most underused design tool: find the layout's *actual* problem (monotone spacing, weak hierarchy, identical card grids) and fix the structure, not the surface.

Hard floors live in `departments/brand/references/uiux-knowledge-and-tools.md` §12 — this file is the craft on top of them, not a restatement.

---

## Spacing scale & rhythm

- **Spacing is a scale, not a value.** Pick one scale. Use it everywhere. Don't type raw px. Values come from a defined set — a framework scale, rem-based tokens, or a custom system — never arbitrary numbers.
- **4pt base, nine steps, named by role, not size.** This is the same base-4px scale as the doctrine hub §3 (`departments/brand/references/uiux-knowledge-and-tools.md`) — one scale, stated once. Prefer 4pt over 8pt: 8pt is too coarse and you'll frequently need 12px between 8 and 16.

```css
:root {
  --space-3xs: 0.125rem;  /*  2px */
  --space-2xs: 0.25rem;   /*  4px */
  --space-xs:  0.5rem;    /*  8px */
  --space-sm:  0.75rem;   /* 12px */
  --space-md:  1rem;      /* 16px */
  --space-lg:  1.5rem;    /* 24px */
  --space-xl:  2.5rem;    /* 40px */
  --space-2xl: 4rem;      /* 64px */
  --space-3xl: 6rem;      /* 96px */
  --space-4xl: 9rem;      /* 144px */
}
```

- Name tokens semantically: `--space-xs` through `--space-4xl`, not `--spacing-8`.
- Use `gap` for sibling spacing. It's cleaner than stacked margins, participates in flex/grid, collapses predictably, and eliminates margin-collapse hacks. Use `margin` only for optical adjustments or breaking out of the flow — never for a list of siblings.
- Apply `clamp()` for fluid spacing that breathes on larger screens.

**Rhythm** is contrast, not uniformity:

- **Tight grouping** for related elements (8–12px between siblings).
- **Generous separation** between distinct sections (48–96px).
- **Varied spacing** within the same layout. If every gap is 24px, the page is a template — mix small, medium, and large gaps; not every row needs the same gap.
- **Density matches content type.** Data-dense UIs need tighter spacing; marketing pages need more air. Too cramped and it suffocates; too sparse and the whitespace is purposeless.
- **Generous top, tight bottom** (or vice-versa). Sections don't need to be evenly padded — if the card padding equals the section padding equals the page padding, the rhythm is flat.

---

## Asymmetry & hierarchy

- A layout has a **primary axis**. Left-biased, right-biased, top-heavy, or bottom-weighted. Centre-biased is a default, not a choice.
- **Asymmetry reads as intentional.** Symmetry reads as generated. When in doubt, shift. But asymmetric composition is a deliberate choice when the content invites it — not a default to chase.
- **Break the grid on purpose.** A page with one element crossing the grid is stronger than a page that never does.

**The squint test.** Blur your (metaphorical) eyes. Can you still identify the most important element, the second most important, and the clear groupings? Does whitespace guide the eye to what matters? If not, the hierarchy is weak regardless of how the colors and fonts look.

Use the fewest dimensions needed for clear hierarchy — space alone can be enough; generous whitespace around an element draws the eye. The best hierarchy combines 2–3 dimensions at once: a heading that's larger, bolder, AND has more space above it reads as primary without trying.

| Tool | Strong Hierarchy | Weak Hierarchy |
|------|------------------|----------------|
| **Size** | 3:1 ratio or more | <2:1 ratio |
| **Weight** | Bold vs Regular | Medium vs Regular |
| **Color** | High contrast | Similar tones |
| **Position** | Top/left (primary) | Bottom/right |
| **Space** | Surrounded by white space | Crowded |

Be aware of reading flow: in LTR languages the eye scans top-left to bottom-right, but primary action placement depends on context (bottom-right in dialogs, top in navigation). Create groupings through proximity and separation.

**Asymmetry techniques:**

- **Wide left margin.** Treat the left as permanent negative space — narrow column of labels, wide column of content. Labels must NOT be section eyebrows / numbers paired with the heading — that's gate-54-banned. Reserve this technique for body-level micro-labels (caption, footnote, date) alongside body copy.
- **Hanging headers.** ⚠️ **Opt-in only.** Section labels sit in the left margin; content flows right. Permitted only when the user explicitly asks for an editorial / hanging-header layout AND no eyebrow / number / chapter tag sits in the left margin. The eyebrow-left / heading-right pattern is banned by slop-test gate 54 — the most reliable templated-editorial AI tell. Default to a stacked single-column section head.
- **Offset grids.** Odd columns wider than even. Or the other way.
- **Grid-breaks.** One element that deliberately extends past a column boundary: a pull-quote, a photograph, a rule, a number.
- **Alignment coherence.** A section head's horizontal alignment should be a deliberate choice that *coheres* with the body it introduces — match it (left head over left-flush body; centred head over symmetric body) or break from it on purpose. The AI mistake is the *accidental* mismatch: a narrow head block auto-centred (`margin-inline: auto` plus a `max-width` / `ch` cap) left floating over full-width, left-flush content. Centred, hanging, bottom-aligned, and asymmetric heads all stay on the table — the guard is intentionality, not uniformity.

**Card discipline:**

- Don't default to card grids for everything; spacing and alignment create visual grouping naturally.
- Use cards only when content is truly distinct and actionable. Never nest cards inside cards — a bordered container inside a bordered container. Pick one; use spacing and dividers for hierarchy within.
- The identical feature grid — three columns, three icons, three two-line headings, three three-line bodies — is *the* AI tell. Vary card sizes, span columns, mix cards with non-card content, use `grid-template-columns: 1.2fr 1fr 0.8fr`, or give items different spans on a 12-column underlying grid.
- Don't default to the hero-metric layout (big number, small label, stats, gradient) as a template. A prominent metric works only when it displays actual data, not decorative numbers.

**Depth:**

- Depth is **weight and scale**, not shadow. A heavier weight, a larger size, a warmer hue — these create hierarchy better than drop shadows. Elevation reinforces hierarchy; it is never decoration.
- If you use shadow, use one from a consistent, subtle scale:
  - **Whisper** — `0 1px 2px oklch(20% 0.01 <hue> / 0.05)` for hovering cards.
  - **Hairline** — `0 0 0 1px oklch(30% 0.01 <hue> / 0.06)` as an alternative to a 1px border.
- Never stack multiple shadows. Never use a coloured glow on a light background; a drop shadow on a dark card creates an accidental glow — that's wrong.

**When in doubt** — if the layout looks fine but flat, do one of these before shipping:

1. Add one break-out element.
2. Unbalance a column width.
3. Move the primary CTA out of the centre.
4. Remove a card and replace it with negative space.
5. Change one section's padding so the rhythm is uneven.

---

## Optical adjustments

- If an icon looks visually off-center despite being geometrically centered, nudge it. But only if you're confident it actually looks wrong — don't adjust speculatively.
- Text at `margin-left: 0` looks slightly indented because of letterform whitespace; a negative margin (`-0.05em`) optically aligns it. Geometrically centered glyphs often look off-center (play icons need to shift right, arrows shift toward their direction).
- Touch targets must be 44×44px minimum even when the visual element is smaller. Expand the hit area with padding or a pseudo-element:

```css
.icon-button { width: 24px; height: 24px; position: relative; }
.icon-button::before {
  content: ''; position: absolute; inset: -10px;
}
```

---

## Container & grid

- **Flexbox for 1D layouts**: rows of items, nav bars, button groups, card contents, most component internals.
- **Grid for 2D layouts**: page-level structure, dashboards, data-dense interfaces, anything where rows AND columns need coordinated control.
- `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` for fluid responsive grids without media queries. On tracks containing images, use `minmax(0, 1fr)`, never bare `1fr` (gate 50).
- Use **named grid areas** (`grid-template-areas`) for complex page layouts; redefine them at breakpoints.
- Use **container queries** for components, viewport queries for page layouts. A card in a narrow sidebar stays compact while the same card in a main content area expands automatically:

```css
.card-container { container-type: inline-size; }
.card { display: grid; gap: var(--space-md); }
@container (min-width: 400px) {
  .card { grid-template-columns: 120px 1fr; }
}
```

- **Page-edge clipping.** Any deliberately overflowing element (clipped-edge hero media, full-bleed marquee, oversized headline — see [`hero-enrichment.md`](hero-enrichment.md) E1/HP2) needs `overflow-x: clip` on both `html` and `body` as the global safety net, with the containing section left `overflow: visible`. Use `clip`, never `hidden`: `clip` preserves `position: sticky`/`fixed` on descendants; `hidden` creates a new scroll container that breaks sticky and can trap focus.
- **Z-index is a named scale**, not freestyle numbers — no `z-index: 9999`.

The layout laws behind these bullets — the z-index level set, the overflow rules, the viewport-unit and width bans — live in the doctrine hub. Point there; don't restate: `departments/brand/references/uiux-knowledge-and-tools.md` §12.

---

## Responsive floors

Mobile-first. Content-driven breakpoints. No desktop-only interactions.

### Non-negotiable widths

Every output must render flawlessly at **320 px, 375 px, 414 px, and 768 px** CSS-pixel widths. Eyeball each viewport before marking the output complete:

- No horizontal scroll (slop-test gate 34)
- No clickable text wrapping to two lines (gate 49)
- No image-bearing grid pushing the layout past viewport — `minmax(0, 1fr)`, never bare `1fr`, on tracks containing images (gate 50)
- Root carries `overflow-x: clip` on both `html` and `body` — never `hidden` (gate 34)
- Display headers wrap inside long words via `overflow-wrap: anywhere; min-width: 0` (gate 51)
- Section heads collapse to one column on mobile across every register variant — per-register overrides need a matching mobile rule (gate 52)
- No scroll-jump on radio-tab clicks — radios in normal flow OR JS guard with `focus({ preventScroll: true })` (gate 53)

This is a hard floor, not a wish list. A page that fails any of these on any of those four widths is not done. Keep this checklist near the screen while building; the design-review skill (`departments/brand/skills/design-review`) audits against it.

### Breakpoints & fluid scaling

- Base styles are for the smallest viewport. `min-width` media queries add as you go up — never `max-width` as the primary direction.
- Breakpoints are where the *content* breaks, not where a device sits. If the headline reflows awkwardly at 720px, that's a breakpoint — regardless of framework defaults.
- Three or four breakpoints, content-driven, in `rem` so they respect the user's font size:

```css
@media (min-width: 40rem) { /* ~640px — tablet, small laptop */ }
@media (min-width: 60rem) { /* ~960px — desktop baseline */ }
@media (min-width: 90rem) { /* ~1440px — wide */ }
```

- Prefer `clamp()` for sizes that change continuously; media queries for layouts that change discretely:

```css
h1 { font-size: clamp(2.5rem, 4vw + 1rem, 6rem); }
.container { padding-inline: clamp(1rem, 4vw, 4rem); }
```

- Use `pointer` and `hover` media queries to detect *interaction capability* instead of width. Never build a mouse-hover interaction that has no touch equivalent:

```css
@media (hover: hover) and (pointer: fine) {
  .card:hover { transform: translateY(-2px); }
}
@media (pointer: coarse) {
  .btn { min-height: 48px; }
}
```

### Mobile collapse discipline — clickable text never wraps

Buttons, primary nav links, footer links, tab labels, breadcrumbs, and CTAs must read as **single-line affordances at every viewport between 320 px and 1920 px**. A button or nav link wrapping to two lines looks broken — visitors read it as a styling error, not as intentional.

```css
/* Affordances are single-line — let the parent reflow, not the label. */
.btn,
.nav__link,
.foot__link,
.cta {
  white-space: nowrap;
}
```

```css
/* When the row can't fit, collapse the row, not the labels. */
@media (max-width: 40rem) {
  .nav__rail { display: none; }         /* desktop nav hides */
  .nav__sheet-toggle { display: grid; } /* mobile menu shows */
}
```

**Order of fixes**, when something does wrap:

1. **Shorten the label.** *"Get started free"* → *"Start free"*. *"Read the documentation"* → *"Read docs"*. *"Schedule a demo"* → *"Book demo"*. Most CTA labels are 30–40 % longer than they need to be.
2. **`white-space: nowrap`** on the affordance, let the parent flex/grid reflow.
3. **`hidden=until-found`** the lowest-priority nav item at narrow widths (it remains in DOM for find-in-page and SEO).
4. **Collapse the nav** into a sheet / off-canvas / disclosure menu below a content-driven breakpoint.

**Never:** let a primary CTA or top-level nav link wrap. Long footer-link labels can wrap *only* in a footer column where wrapping is part of the column's rhythm — not in an inline footer link strip.

### Small-screen residue

- `dvh` / `svh` / `lvh` instead of `vh` for heights that interact with mobile chrome; never `width: 100vw` (scrollbar overflow) — use `width: 100%` with padding.
- Safe areas for iOS notch / Android nav bars: `viewport-fit=cover` on the meta viewport plus `padding-inline: max(1rem, env(safe-area-inset-left))` and `padding-bottom: max(1rem, env(safe-area-inset-bottom))`.
- Tables that won't fit: collapse to cards (`display: block` on `<tr>` + `data-label` via `::before`) — or better, redesign the data; tables are rarely the right mobile representation.
- Images: `srcset` with width descriptors, `<picture>` for art direction, `loading="lazy"` below the fold, and `width`/`height` attributes on every image to avoid CLS.
- Internationalisation: reserve 30–40% extra horizontal space for German, Russian, and Finnish; use logical properties (`margin-inline-start`, `padding-block`, `border-inline-end`) so RTL comes for free; don't hard-code language-specific punctuation or date formats.

---

## Verify

Answer each item by citing the file, selector, or value that satisfies it — never a bare yes:

- **Squint test**: primary, secondary, and groupings identifiable with blurred vision?
- **Rhythm**: a satisfying beat of tight and generous spacing?
- **Hierarchy**: the most important content obvious within 2 seconds?
- **Breathing room**: comfortable, not cramped or wasteful?
- **Consistency**: the spacing system applied uniformly, no off-scale values?
- **Responsiveness**: graceful at 320 / 375 / 414 / 768 px, floors above all green?

A clean mechanical pass is a floor, not a verdict: a monotone grid with uniform spacing passes every lint rule, which is exactly what the squint test exists to catch.
