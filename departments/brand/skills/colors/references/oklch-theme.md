# OKLCH Theme Construction

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT —
> Copyright (c) 2026 Hallmark contributors) `references/custom-theme.md`
> and [impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0 —
> Copyright Paul Bakaus) `skill/reference/colorize.md`. License texts at
> `departments/brand/skills/design-review/references/` (`hallmark.LICENSE`,
> `impeccable.LICENSE`, `impeccable.NOTICE`). Upstream stamps renamed to
> `[arka:design-dna]`; project memory relocated to `.arka/design/log.json`.

A custom theme is **made-to-measure for one brief**, written inline into the
page's `:root`, never a permanent catalog entry. It spans a spectrum of
depth: at its lightest, a complete OKLCH palette + free-font pairing tuned
to the brief while keeping the project's existing structures (the
*combination* is per-brief); at its fullest — **bespoke** — the page's
structure and composition are designed from first principles too. One
route, chosen depth. Every palette below is built in OKLCH, never HSL
(rationale in § Why OKLCH). <!-- rule:theme-oklch-only -->

**The freedom is the combination — never the floor.** Every contrast,
ban-list, and slop-test constraint still applies at every depth — the
gates are the floor that never moves (gates:
`departments/brand/skills/design-review/references/slop-test.md`; ban-list:
hub §11, `departments/brand/references/uiux-knowledge-and-tools.md`). The
palette + pairing surface in plain text *before* any code is emitted (the
token-plan-then-critique loop, hub §8), so the user can redirect early.
<!-- rule:theme-preview-before-code -->

**Register split** (see
`departments/brand/skills/design-review/references/design-registers.md`):
on **brand** surfaces the palette IS voice — pick a color strategy first
(Restrained / Committed / Full palette / Drenched, hub §12) and follow its
dosage; Committed, Full palette, and Drenched deliberately exceed the ≤10%
accent rule, and a dominant color can own the page when the strategy calls
for it. On **product** surfaces color is semantic-first and almost always
Restrained: accent is reserved for primary action, current selection, and
state indicators — not decoration — and every color keeps one consistent
meaning across every screen. More color ≠ better; strategic color beats
rainbow vomit. <!-- rule:theme-register-split -->

---

## When to construct a custom theme — trigger signals

Do not offer custom-vs-existing on every prompt; that's friction, not
discipline. The default route is the project's design system or a curated
aesthetic direction (hub §10). Construct a custom OKLCH theme only when
one of these signals fires:

1. **Explicit ask** — "custom theme", "tailored to our brand", "make it
   ours", "something unique", "I want my own palette".
2. **Named brand colour** — a specific anchor as hex / OKLCH / name
   ("use our terracotta", "the brand red is #c0392b", "anchor on sea-blue").
3. **Multi-attribute aesthetic no existing direction carries** — three or
   more vibe words pointing at a specific, off-catalog feel ("moss, lichen,
   soft pink, herbal" · "sun-drenched, market-day, carbon-black"). One
   adjective ("warm", "technical", "playful") is not a signal — that's a
   tone any direction already carries.
4. **Brand-mood reference attached** — a colour swatch, moodboard, or
   Pantone chip. (A *page* screenshot is a design-DNA study ask — route to
   design-review/refine; custom is for brand colour and mood.)
5. **A singular structural vision** — the brief names a structure or
   composition, not just a palette/mood ("from scratch", "ignore the
   catalog", a scroll-assembling poem, a ticket-shaped page). Routes to
   the **bespoke depth** (§ Bespoke depth below).

If a signal fires, confirm the route in one short question and wait.
Silence routes to the default, not to custom. If no signal fires, do not
mention the fork at all.

## The one follow-up question

Once custom is confirmed, ask **one** thing in **one** message:

> *"Custom needs one input — describe the brand's vibe in 4–8 words.
> Examples: 'archival warmth, hand-set, no varnish' · 'industrial
> precision, cool, technical' · 'moss, lichen, soft pink, herbal'.
> Optional second input: an anchor colour — hex, OKLCH, or a name like
> 'terracotta', 'sea-blue'. If you skip it, I'll pick one from the vibe."*

**Do not ask anything else.** Audience / use / tone plus the brand vibe is
already enough signal. The model has no business asking the user to
nominate paper lightness or font weights — that's the model's job. If the
user gives a paragraph, accept it but compress to 4–8 words for the stamp.

---

## Palette construction — the algorithm

Build the palette in this order. Each step cites the rule it obeys — do
not restate the rule, just apply it.

### 1 · Anchor accent first

- Convert the user's named or hex anchor into OKLCH.
- Clamp chroma to **0.12–0.20**. <!-- rule:theme-anchor-chroma-clamp -->
- If the user skipped the anchor: derive hue from the vibe — *warmth* →
  30–60° · *technical/industrial* → 220–250° · *botanical/moss* → 130–160° ·
  *late-night/neon* → 280–320° · *sun-drenched/market* → 60–80° amber. Keep
  chroma 0.12–0.16 (mid-saturation; saturation comes from contrast against
  neutral, not from chroma).
- **One accent, strictly.** When the vibe names two hues, one becomes the
  accent and the other becomes the paper/neutral tint (see the Mossroot
  worked example). <!-- rule:theme-single-accent -->

### 2 · Paper

- Derive paper L from the vibe: <!-- rule:theme-paper-bands -->
  - bright/airy/breakfast/hand-set → **L 95–98%** (warm-tinted)
  - archival/editorial/restrained → **L 92–95%** (warm-tinted)
  - technical/clinical/spec-sheet → **L 98–100% near-white** (cool-tinted;
    can equal #fff but tinted neutrals downstream)
  - dark/restless/late-night/manifesto → **L 12–18%** (anchor-tinted)
- **Always tint paper toward the anchor hue with chroma 0.005–0.020.**
  Pure-white #fff is allowed only when ink + accent + greys carry the
  chroma; the paper itself never carries chroma 0 in *both* directions.
  Watch the warm-neutral tell: the generic cream/sand band is the
  saturated AI default (law: hub §12) — tint toward *this brand's* anchor,
  not toward "warm" by reflex. <!-- rule:theme-paper-tint -->
- Paper-2 (one elevation step): step ±2–4% L from paper.
- Paper-3 (optional second step): step ±5–7% L from paper. Skip on
  minimal palettes.

### 3 · Ink

- If paper L < 50: ink L **88–96%**. <!-- rule:theme-ink-bands -->
- If paper L ≥ 50: ink L **16–24%**.
- Tint ink chroma **0.005–0.014** toward anchor (a shade darker / lighter,
  never neutral).
- Ink-2 (secondary text): step 4–8% L away from ink toward paper. Same
  hue family.

### 4 · Supporting greys

Step by ~6–10% L between paper and ink, all tinted toward anchor with
chroma 0.005–0.018: <!-- rule:theme-grey-ladder -->

- `--color-rule` — dividers · L ~70–82% (light paper) or ~26–34% (dark paper).
- `--color-rule-2` — secondary dividers · 4–6% L closer to paper than rule.
- `--color-muted` — de-emphasised text · L ~38–56%.
- `--color-neutral` — mid-grey equivalent · L ~30–56%.

These are not arbitrary. The L-step gives the palette **typographic
depth** without leaning on accent. Muted text must still clear body
contrast (law: hub §12 — muted-gray-on-tinted-near-white is the single
biggest readability failure).

### 5 · Focus

- Same hue as accent, slightly higher chroma (0.18–0.22) for visibility.
- Same L as accent ±5%.
- Used only on `:focus-visible` — the ring must show instantly, never
  animate in (see
  `departments/dev/skills/animated-website/references/motion-recipes.md`).
  <!-- rule:theme-focus-token -->

### 6 · Accent-ink (overlay text colour on accent)

- If accent L > 50: use ink (text reads dark on accent fill).
- If accent L ≤ 50: use paper (text reads light on accent fill).
- Verify contrast ≥ 7:1 for body-size text on accent, ≥ 3:1 for large
  text. Text and fill must also differ by > 5% lightness or > 0.05 chroma
  in OKLCH — the check that catches the black-on-black button bug
  (law: hub §12). <!-- rule:theme-accent-ink-contrast -->

### 7 · Verification

Named checks — the full gate battery lives in
`departments/brand/skills/design-review/references/slop-test.md`:

- **No pure #000/#fff base**: paper and ink both have chroma > 0.
  <!-- rule:theme-verify-no-pure-extremes -->
- **No zero-chroma neutrals**: every grey has chroma ≥ 0.005.
  <!-- rule:theme-verify-tinted-greys -->
- **Accent stays a signal**: plan the accent's role on the page (active
  state, one wordmark dot, one CTA fill) — don't carpet a section in
  accent. This is the Restrained-strategy default; when the brief picks
  Committed / Full palette / Drenched (hub §12), the chosen strategy
  governs dosage instead — the footprint cap is Restrained-only.
  <!-- rule:theme-accent-footprint -->

---

## Cross-tone font pairing

The palette carries the temperature; the pairing carries the voice.
Tone-pairing tables group faces by tone (Editorial, Technical, Brutalist,
Soft, Luxury, Playful, Austere, Workshop), each with a free baseline and a
paid upgrade. Catalog pairings match Display-from-tone-X with
Body-from-tone-X. **Custom can mix tones — that's the whole point:**
<!-- rule:theme-cross-tone-pairing -->

- Editorial display + Technical body (italic Fraunces wordmark + Geist
  body) — an academic-tone SaaS.
- Brutalist display + Editorial body (Anton + Newsreader italic) — a
  left-leaning manifesto magazine.
- Playful display + Austere body (Bricolage Grotesque + Inter Tight) — a
  creator-tool brand.
- Luxury display + Technical body (Cormorant Garamond + JetBrains Mono) —
  a hand-crafted dev-tool.

Pick **one display face** and **one body face** from any tone's columns.
Optional mono if the page has code or tabular data.

The discipline:

- **Free baseline only** unless the user has confirmed paid licences.
  Never name a paid font in code without confirming the licence.
  <!-- rule:theme-free-fonts-only -->
- **The reflex-reject list still applies** — the canonical font ban-list
  is hub §11 (`departments/brand/references/uiux-knowledge-and-tools.md`).
  Several faces named in this file's examples sit on that list (Fraunces,
  Newsreader, Cormorant Garamond…): using one is legal only as a
  *deliberate pick with a stated reason* — §11's carve-out. Reflex is the
  crime, not the font.
- **Variable fonts are preferred** when available — they support
  optical-size and weight axes for tighter typographic control.
- **The pair must read.** Before committing, mentally render the page:
  does the display face have enough weight contrast (200/400 next to
  700/900)? Does the body face read at ≥ 1rem across a 45–75ch measure?
  Mono display + mono body is allowed only when the single font IS the
  design (terminal aesthetic, true specimen). If any answer is no,
  redirect — pick a different body face or shift the display weight.

Pairing depth — tone tables, free-vs-paid columns, sizes, tracking, and
weight systems — lives in
`departments/brand/skills/design-system/references/typography-craft.md`.

---

## Theme axes — declare them for diversification

A custom theme must declare its three diversification axes explicitly so
the structural-diversification rule (hub §9: consecutive outputs must
differ on at least one axis) fires the same way it does on named themes.
<!-- rule:theme-axes-declared -->

**Paper band** — `dark` (paper L < 30%) · `mid` (L 30–85%) · `light`
(L > 85%).

**Display style** — pick one for the chosen display face:
`italic-serif` (Fraunces italic, Newsreader italic, EB Garamond italic) ·
`roman-serif` (Source Serif 4, Crimson Pro, Bitter, Cardo) ·
`geometric-sans` (Geist, Bricolage Grotesque, Manrope, Sora) ·
`mono` (Geist Mono, JetBrains Mono) ·
`display-condensed-italic` (Migra italic, Tobias italic) ·
`display-condensed-bold` (Anton, Bebas Neue, Oswald) ·
`display-heavy` (Inter Tight 900, Bricolage 800, Druk-class) ·
`slab-serif` (Roboto Slab, Bitter heavy, Zilla Slab) ·
`system-native` (austere) · `risograph-bold` · `handwritten` (rare; only
when the brand demands).

**Accent hue band** — `warm` (hue 10–60°) · `cool` (hue 200–300°) ·
`neutral` (no chromatic accent; chroma < 0.05) · `chromatic-other`
(anything else — sub-tag the anchor: `chromatic-green ~145°` ·
`chromatic-terracotta ~30°` · `chromatic-dusty-pink ~350°` ·
`chromatic-moss ~140°` · `chromatic-amber ~75°`).

Write all three into the `[arka:design-dna]` stamp and the
`.arka/design/log.json` entry (below). They are the durable record; the
next run reads them. A custom run that follows another custom run must
differ on at least one axis; a custom run that follows a catalog run must
differ from the catalog theme's axes. The diversification rule is
theme-route-blind. <!-- rule:theme-diversification -->

---

## Bespoke depth — custom that designs the whole page

Most custom runs are *tuned* (a palette + pairing on existing structures).
**Bespoke** is the deep end, fired by trigger signal 5: the brief's
*structure itself* is the ask and no catalog shape fits. At this depth
custom designs the page from first principles — palette, type, **and**
composition — and the only thing it inherits is the floor.

Confirm the route once (default to the catalog on silence), then take
**one** input: *"the direction in a sentence or two — what should this
page feel like and do that an off-the-shelf theme wouldn't?"*

**It drops** (only at this depth): the named-theme tokens (write the
palette inline for this page only — the algorithm above still governs
*how*); the genre-cluster routing; the fixed macrostructure catalog
(compose the page's structure for the brief — a novel hero, nav, or
section is *encouraged* when it serves the idea); the diversification
rotation (bespoke is a one-off, though it shouldn't clone a recent
bespoke run).

**It keeps** — the non-negotiable floor, identical to tuned custom: every
slop-test gate (`design-review/references/slop-test.md`); accessibility &
contrast (WCAG), a visible `:focus-visible`, `prefers-reduced-motion`,
semantic landmarks, alt text; the font ban-list (hub §11) and
free-baseline discipline; the OKLCH palette discipline above (tinted
neutrals, no pure #000/#fff, accent kept to a signal unless the strategy
earns more); one orchestrated motion; the preview before code; the stamp
+ log.

**Process:** read the brief + the one-line direction → design the *system
and the one central move* (the idea that makes it not-a-template) → run
the gates *as you compose* → surface the preview (palette, type,
structure, central idea) → build, stamp, log. Bespoke is **more** design
judgment, not less — a bespoke page that reads generic, or trips a gate,
has failed; re-design.

**Bespoke is rare.** Most briefs use the project system or a curated
direction; some are tuned custom; few are bespoke. Reaching for bespoke
on a vanilla brief is over-reach.

---

## Stamp and log — the durable record

The produced stylesheet opens with the `[arka:design-dna]` companion
stamp (hub §9 — key=value, single line, greppable; the six pre-emit
critique scores are appended when the §8 critique runs). Custom runs add
`theme=custom`, `vibe`, `paper`, and `axes` keys:

```css
/* [arka:design-dna] macrostructure=<name> theme=custom vibe="<4–8 words>" paper=oklch(<L> <C> <H>) anchor=oklch(<L> <C> <H>) display=<font> body=<font> axes=<paper-band>/<display-style>/<accent-hue> critique=P#H#E#S#R#V# */
```

Bespoke runs record the structure and the central idea instead of a
catalog macrostructure:

```css
/* [arka:design-dna] macrostructure=bespoke structure="<one-line shape>" idea="<central move>" theme=custom paper=oklch(...) anchor=oklch(...) display=<font> body=<font> axes=<paper-band>/<display-style>/<accent-hue> critique=P#H#E#S#R#V# */
```

Custom runs extend the `.arka/design/log.json` schema with a `theme_axes`
field and an optional `vibe` field:

```json
{ "date": "2026-05-01",
  "macrostructure": "Stat-Led",
  "theme": "custom",
  "theme_axes": "light / italic-serif / chromatic-terracotta",
  "vibe": "archival warmth, hand-set, no varnish",
  "enrichment": "none",
  "brief": "Coffeebox · subscription" }
```

Catalog entries continue to record `theme: <name>` and skip `theme_axes`.
The diversification check reads axes from the entry for custom runs and
from the theme definition for catalog runs.

---

## Three worked examples

Concrete generations to seed imitation. Each shows the brief, the vibe
answer, the constructed palette, the chosen pair, and the stamp.

### Archival café — "Coffeebox"

**Brief:** *"Build me a landing page for Coffeebox — a small-batch coffee
subscription. Roast on Sunday, ship on Monday, drink Tuesday. Audience:
people who already buy good coffee and want fewer trips to the shop.
Tone: warm, hand-set, editorial — like a small café's chalkboard. Theme
route: custom."*

**Vibe answer:** *"archival warmth, hand-set, no varnish."*
**Anchor:** *"terracotta."*

**Palette:**
- paper `oklch(94% 0.020 65)` — warm-cream, hue 65 (amber-warm)
- paper-2 `oklch(91% 0.022 65)` — one elevation step
- ink `oklch(22% 0.014 60)` — warm dark brown-black
- ink-2 `oklch(40% 0.014 60)` — warm secondary
- rule `oklch(78% 0.018 65)` — warm hairline
- muted `oklch(54% 0.014 60)` — warm grey
- accent `oklch(58% 0.16 35)` — terracotta (hue 35, chroma 0.16)
- accent-ink `oklch(96% 0.014 65)` — paper for text on accent
- focus `oklch(56% 0.20 35)` — accent at higher chroma

**Pair:** display **Fraunces italic** (Editorial, free) · body **Source
Serif 4** (Editorial, free) · mono **JetBrains Mono** (Technical, free).
Fraunces is on the hub §11 reflex-reject list — this is a deliberate pick
for a stated hand-set editorial brief, i.e. the §11 carve-out. Note also
that warm-cream + serif + terracotta brushes the hub §8 default look:
legal here because the brief *pins* it ("warm, hand-set, editorial");
never spend a free axis on it.

**Axes:** **light / italic-serif / chromatic-terracotta**.

**Stamp:**
```css
/* [arka:design-dna] macrostructure=Long-Document theme=custom vibe="archival warmth, hand-set, no varnish" paper=oklch(94% 0.020 65) anchor=oklch(58% 0.16 35) display=Fraunces-italic body=Source-Serif-4 axes=light/italic-serif/chromatic-terracotta */
```

### Industrial fintech — "Loop"

**Brief:** *"Loop is a real-time payment-rail observability platform for
fintechs. Audience: platform engineers. Use case: try it / contact sales.
Tone: industrial, cool, technical. Theme route: custom."*

**Vibe answer:** *"industrial precision, cool, technical."*
**Anchor:** *"sea-blue."*

**Palette:**
- paper `oklch(13% 0.012 220)` — dark cool
- paper-2 `oklch(17% 0.014 220)` — one step up
- paper-3 `oklch(22% 0.014 220)` — two steps up (panels)
- ink `oklch(94% 0.010 220)` — cool light
- ink-2 `oklch(72% 0.010 220)`
- rule `oklch(30% 0.012 220)`
- muted `oklch(58% 0.012 220)`
- accent `oklch(72% 0.16 220)` — sea-blue (cool)
- focus `oklch(78% 0.20 220)`

**Pair:** display **Geist Mono 500** (Technical, free) · body **Geist**
(Technical, free) · mono **Geist Mono** (Technical, free).

Note: this *is* a single-family page (Geist + Geist Mono are the same
family at different widths). Single-font pages are allowed only when the
single font IS the design choice — for an industrial-precision fintech,
it is.

**Axes:** **dark / mono / cool**.

**Stamp:**
```css
/* [arka:design-dna] macrostructure=Workbench theme=custom vibe="industrial precision, cool, technical" paper=oklch(13% 0.012 220) anchor=oklch(72% 0.16 220) display=Geist-Mono-500 body=Geist axes=dark/mono/cool */
```

### Botanical apothecary — "Mossroot"

**Brief:** *"Mossroot is a small herbal apothecary in Porto. We make
tinctures, salves, and tea blends. Audience: locals + visitors. Use: see
what we make + visit. Tone: quiet, herbal, hand-poured. Theme route:
custom."*

**Vibe answer:** *"moss, lichen, soft pink, herbal."*
**Anchor:** *(skipped — pick from vibe)*.

The vibe names two hues: *moss* (greenish, ~140°) and *soft pink* (warm,
~350°). Pick **soft pink as the accent** (single anchor — custom is
one-accent strict) and use the moss-green as the *paper tint* (chroma
0.018 toward 145°). This carries the dual-vibe without splitting accent.

**Palette:**
- paper `oklch(96% 0.018 145)` — moss-tinted near-white
- paper-2 `oklch(93% 0.020 145)`
- ink `oklch(22% 0.014 140)` — moss-tinted dark
- ink-2 `oklch(42% 0.014 140)`
- rule `oklch(82% 0.018 145)`
- muted `oklch(56% 0.014 140)`
- accent `oklch(72% 0.13 350)` — dusty-pink (chromatic-other)
- focus `oklch(70% 0.18 350)`

**Pair:** display **Cormorant Garamond** (Luxury, free) · body **EB
Garamond** (Luxury, free) · mono **Geist Mono** (rare on this page; only
for ingredient lists). Cormorant Garamond is §11-listed — deliberate pick
for a quiet, hand-poured luxury register; state the reason in the plan.

**Axes:** **light / roman-serif / chromatic-other (dusty-pink)**.

**Stamp:**
```css
/* [arka:design-dna] macrostructure=Catalogue theme=custom vibe="moss, lichen, soft pink, herbal" paper=oklch(96% 0.018 145) anchor=oklch(72% 0.13 350) display=Cormorant-Garamond body=EB-Garamond axes=light/roman-serif/chromatic-other-dusty-pink */
```

---

## Why OKLCH — stop using HSL

**Stop using HSL.** Use OKLCH (or LCH) instead. It's perceptually
uniform: equal steps in lightness *look* equal, unlike HSL where 50%
lightness in yellow looks bright while 50% in blue looks dark.

`oklch(lightness chroma hue)` — lightness 0–100%, chroma roughly 0–0.4,
hue 0–360. To build a colour and its lighter/darker variants, hold
chroma + hue roughly constant and vary the lightness, but **reduce chroma
as you approach white or black** — high chroma at extreme lightness looks
garish.

The hue you pick is a brand decision and should not come from a default.
Do not reach for blue (hue 250) or warm orange (hue 60) by reflex; those
are the dominant AI-design defaults, not the right answer for any
specific brand.

## Tinted neutrals — why the algorithm tints everything

**Pure gray is dead.** A neutral with zero chroma feels lifeless next to
a coloured brand. That is why every step of the algorithm above tints
toward the anchor: add a tiny chroma value (0.005–0.015; paper may reach
0.020 on warm atmospheric briefs) to all neutrals, hued toward the brand
colour (law: hub §12). The chroma is small enough not to read as "tinted"
consciously, but it creates subconscious cohesion between brand colour
and UI surfaces. <!-- rule:theme-tinted-neutrals-rationale -->

The hue you tint toward comes from THIS project's brand, not from a
"warm = friendly, cool = tech" formula. If the brand colour is teal, the
neutrals lean teal; if amber, they lean amber. **Avoid** the trap of
always tinting warm-orange or always cool-blue — those are the two
laziest defaults and they create their own monoculture across projects.
The generic warm tint (`oklch(97% 0.01 60)` and neighbours) is now the AI
cream/sand giveaway: be specific to the brand or stay neutral.

## Gray on colour

Never put gray text on coloured backgrounds — it looks washed out (law:
hub §12). Use a darker shade of the background's own hue, or a
transparency of the text colour, so the "muted" step stays inside the
fill's colour family. This is why the algorithm derives accent-ink from
paper or ink (same hue family) rather than from a neutral.
<!-- rule:theme-gray-on-color -->

## Alpha is a design smell

Heavy use of transparency (`rgba`, `hsla`, low-alpha `oklch`) usually
means an incomplete palette. Alpha creates unpredictable contrast,
performance overhead, and inconsistency. The grey ladder above exists so
you never need it: define explicit overlay colours for each context
instead. Exception: focus rings and interactive states where see-through
is genuinely needed (law: hub §12). <!-- rule:theme-alpha-smell -->

## Dark mode is not inverted light mode

You can't just swap colours. Dark mode requires different design
decisions: <!-- rule:theme-dark-mode-surfaces -->

| Light mode | Dark mode |
|------------|-----------|
| Shadows for depth | Lighter surfaces for depth (no shadows) |
| Dark text on light | Light text on dark (reduce font weight) |
| Vibrant accents | Desaturate accents slightly |
| White backgrounds | Either pure black or a deep surface that fits the brand (a brand-tinted near-black at oklch 12–18% — the algorithm's dark paper band) |

In dark mode, depth comes from surface lightness, not shadow. Build a
3-step surface scale where higher elevations are lighter (the paper /
paper-2 / paper-3 ladder — e.g. 15% / 20% / 25% L). Use the SAME hue and
chroma as the brand anchor (whatever it is for THIS project; do not reach
for blue) and only vary the lightness. Reduce body text weight slightly
(e.g. 350 instead of 400): light text on dark reads heavier than dark
text on light. <!-- rule:theme-dark-mode-body-weight -->

**Token hierarchy:** use two layers — primitive tokens (`--blue-500`) and
semantic tokens (`--color-primary: var(--blue-500)`). For dark mode,
redefine only the semantic layer; primitives stay the same.

---

## What custom does **not** do (worth restating)

1. **Does not invent themes that ignore the rules.** Every paper L band,
   accent chroma cap, neutral-tinting requirement, font ban (hub §11), and
   slop-test gate carries forward. The freedom is the *combination* — not
   the rules.
2. **Does not save themes for reuse.** A custom run is per-output; the
   skill does not write back to any shared token file. If the user wants a
   permanent theme, they promote the palette into the project's design
   system themselves and name it. <!-- rule:theme-no-permanent-themes -->
3. **Does not ask multiple follow-up questions.** One vibe answer
   (+ optional anchor) is enough — the brief plus the structure pick
   already give 80% of the signal.
4. **Does not relax the diversification rule.** Custom entries declare
   their three axes the same way catalog entries do; the rotation fires on
   both, theme-route-blind.
5. **Does not bypass the preview.** The palette + pairing surface in
   plain text *before* any code is emitted (hub §8 loop), so the user can
   redirect early.

If any of those five lines is bent, the custom output is over-invented.
Audit it; redirect.
