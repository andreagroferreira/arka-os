# Typography craft

> Source: merge of `references/typography.md` from the **hallmark** skill repo (MIT — see `hallmark.LICENSE` in this references directory) and `skill/reference/typeset.md` from the **impeccable** repo (Apache-2.0 — see `impeccable.LICENSE` in this references directory). The 2+1 rule, font catalog, and hero-sizing brackets are hallmark's; the brand-vs-product register, fixed-rem-vs-fluid doctrine, and web-font-loading craft are impeccable's. Banned/overused font lists live ONLY in `departments/brand/references/uiux-knowledge-and-tools.md` §11 — this file points there and never restates them. Generic font-pairing data (who pairs with whom, with no ban or theme semantics) is owned by the `ui-ux-pro-max` plugin skill. Rule anchors follow impeccable's `<!-- rule:… -->` convention (the two source files carried none; the IDs below are minted for this port). Upstream hallmark ships an in-repo face ("The Future") as its default body workhorse; that font is not bundled here — wherever the source referred to it, read *the project's chosen body workhorse*.

Type carries the design. If the type is wrong, nothing else matters. Typography carries most of the information on the page — replace generic defaults (a reflex sans at a flat scale) with type that reflects the brand and scales with intentional contrast.

## Principles

- A page is a pairing, not a single font. Display face + body face, minimum. *Single-font pages are allowed only when the single font IS the design choice* — a true terminal aesthetic is monospace-everywhere on purpose; a Manifesto poster might be one display face on purpose. The default is a pairing.
- Commit to extremes. Weight 200 next to weight 800 reads as intentional. Weight 400 next to weight 600 reads as a default setting.
- Size steps should be ratios, not increments. Major third (1.25), perfect fourth (1.333), perfect fifth (1.5), or golden (1.618). Pick one and use it. The common mistake is too many font sizes too close together (14px, 15px, 16px, 18px…) — muddy hierarchy. Use fewer sizes with more contrast; 5 sizes cover most needs (caption, secondary, body, subheading, heading). <!-- rule:type-modular-scale -->
- Line-height changes with size. Tight for display (1.05–1.2), comfortable for body (1.5–1.65).
- Measure — line length — lives between 45 and 75 characters. Use `max-width: 65ch` as the default.
- Combine dimensions for hierarchy: size + weight + colour + space. Don't rely on size alone.
- Good typography is invisible; bad typography is distracting. The goal isn't "fancier" — it's clearer, more readable, more intentional.

## Register — brand vs product

Two registers, two sizing strategies: <!-- rule:type-register-split -->

- **Brand / marketing / content pages:** expressive faces are the point. Fluid `clamp()` scale for headings and display, ≥ 1.25 ratio between steps. Body text stays fixed even here — the size difference across viewports is too small to warrant fluidity.
- **Product UI (apps, dashboards, data-dense interfaces):** system fonts and familiar sans stacks are legitimate. One well-tuned family typically carries the whole UI. Fixed `rem` scale, 1.125–1.2 ratio between more closely-spaced steps, optionally adjusted at 1–2 breakpoints.

**Fixed rem vs fluid clamp — the doctrine.** No major app design system (Material, Polaris, Primer, Carbon) uses fluid type in product UI; fixed scales give the spatial predictability that dense, container-based layouts need. A fluid h1 that shrinks in a sidebar looks worse, not better. Use fluid type only for headings and display text on marketing/content pages where text dominates the layout and needs to breathe across viewport sizes. <!-- rule:type-fixed-rem-product -->

Fluid type mechanics, when it IS the right call:

- `clamp(min, preferred, max)` — the middle value (e.g. `5vw + 1rem`) controls scaling rate; add a rem offset so it doesn't collapse to 0 on small screens.
- **Bound your clamp(): keep `max ≤ ~2.5 × min`.** Wider ratios break the browser's zoom and reflow behaviour and make large viewports feel like the page is shouting. <!-- rule:type-clamp-max-2-5x -->
- **Scale container width and font-size together** so effective character measure stays in the 45–75ch band at every viewport. A heading that widens faster than its container drifts out of the comfortable measure at the top end.

## The 2+1 rule — three faces is the ceiling

**A page may use at most three distinct font families.** One **display**, one **body**, and an optional **outlier** for a single typographic moment — wordmark, hero stat, pull quote, masthead — where the page wants exactly one note that doesn't sound like the rest. Four families is slop. Two is canonical. Three is the ceiling, used sparingly. <!-- rule:type-two-plus-one -->

The pattern:

```css
:root {
  --font-display:  "Fraunces", ui-serif, Georgia, serif;       /* headings, hero */
  --font-body:     "Geist", ui-sans-serif, system-ui, sans;    /* prose, UI */
  --font-outlier:  "Geist Mono", ui-monospace, monospace;      /* wordmark + hero stat ONLY */
}
```

The outlier is a *register*, not a third surface. Rules:

- **Outlier appears in ≤ 2 places** on the whole page. Wordmark + hero stat. Or pull quote + masthead. Two slots, not five. If you find yourself reaching for it a third time, you don't have an outlier — you have a third body font, which is slop.
- **The outlier carries one role.** It tags a specific kind of content (the brand, the headline figure, the manifesto line). Once you know what it tags, every instance of that role uses it. Don't apply it to one button label and not another.
- **Mono counts as a face.** A page with Fraunces display, Geist body, and Geist Mono in code blocks is using three families. That's fine — code is the outlier role. Don't sneak in a fourth.
- **Same family at different weights is one family**, not two. Geist 400 + Geist 700 is one font; pairing it with Fraunces is two. Adding Geist Mono on top is three.

Two families is still the right answer for most pages. Three is for SaaS / brand-heavy / editorial-rich pages where the wordmark needs a different register than the body. In product UI, one family is often right — a well-tuned sans carries headings, buttons, labels, body, and data.

## Banned defaults

The canonical banned/overused font list (the reflex sans, serif, and mono defaults every LLM reaches for) lives in **`departments/brand/references/uiux-knowledge-and-tools.md` §11** — the single home for ban lists. Consult it before naming any face; never restate it here or anywhere else. <!-- rule:type-ban-list-canonical-home -->

If the user insists on a banned face, do it — the ban is against *reflex* defaults, not against informed choices. Otherwise pick from the catalog below.

Anti-reflexes worth defending against (these are judgement corrections, not bans):

- A technical/utilitarian brief does NOT need a serif "for warmth." Most tech tools should look like tech tools.
- An editorial/premium brief does NOT need the same expressive serif everyone is using right now. Premium can be Swiss-modern, neo-grotesque, a literal monospace, or a quiet humanist sans.
- A children's product does NOT need a rounded display font. Kids' books use real type.
- A "modern" brief does NOT need a geometric sans. The most modern thing you can do is not use the font everyone else is using.
- System fonts are underrated: `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui` looks native, loads instantly, and is highly readable. Consider it for apps where performance > personality — but never as the *only* stack on brand surfaces.

## The font catalog

Three sources, in priority order:

- **Google Fonts** — free, served via CDN, works everywhere. The default source.
- **Fontshare** (Indian Type Foundry) — free for commercial use, foundry-grade. The "you didn't know these were free" tier. Drop-in via `<link href="https://api.fontshare.com/v2/css?f=...">`.
- **Foundry-licensed** — Klim, Pangram Pangram, Production Type, Lineto, Colophon. Only when the user has confirmed they're licensed.

### Free display faces

| Family | Source | Voice | Best for |
| --- | --- | --- | --- |
| **Fraunces** | Google | Variable serif, deeply expressive italic, optical-size axis | Editorial, Atelier, brand-heavy |
| **Newsreader** | Google | Roman serif with optical-size + italic | Editorial, magazine, long-form |
| **Instrument Serif** | Google | Tight contrast, italic available, smart for short heads | Brand, atelier, intimate editorial |
| **Cormorant Garamond** | Google | Classical, high contrast, luxury register | Luxury, fashion, fine arts |
| **EB Garamond** | Google | Honest classical Garamond, body-grade | Editorial body, longform reading |
| **Cardo** | Google | Scholarly serif, generous x-height | Reference, academic, slow reading |
| **Source Serif 4** | Google | Modern transitional, big OT family | SaaS marketing with serif tone |
| **DM Serif Display** | Google | Bracketed serif, high-contrast display | Headlines that need to feel printed |
| **Bodoni Moda** | Google | Modern Bodoni revival, dramatic | Fashion, editorial, luxury display |
| **Playfair Display** | Google | Use only as display; banned as body (see §11) | Marketing display moments — sparingly |
| **Geist** | Google | Modern grotesque, geometric, 7 weights | Modern minimal, SaaS, dev tools |
| **Inter Tight** | Google | Tighter Inter — allowed *only* as a body fallback in technical themes; never as display | UI body in restrained themes |
| **Bricolage Grotesque** | Google | Variable display sans, bold weights, condensable | Brutal, playful, riso-bold |
| **Space Grotesk** | Google | Geometric grotesque, slightly quirky | Brutalist, technical |
| **Anton** | Google | Heavy condensed grotesque | Posters, manifestos |
| **Big Shoulders Display** | Google | Industrial condensed | Sports, manifestos, declarative |
| **Tomorrow** | Google | Variable optical condensed | Tech, atmospheric, near-future |
| **Outfit** | Google | Modern geometric (a reflex default — use only when *picked* deliberately) | Restrained tech — sparingly |
| **General Sans** | Fontshare | Modern grotesque, Geist-adjacent | Modern minimal alternative to Geist |
| **Switzer** | Fontshare | Neutral sans, broad weight range | SaaS body, restrained |
| **Cabinet Grotesk** | Fontshare | Display grotesque, 9 weights | Editorial display, magazine |
| **Clash Display** | Fontshare | Ultra-condensed display | Posters, brand moments |
| **Satoshi** | Fontshare | Playful geometric sans | Playful, consumer |
| **Sentient** | Fontshare | Variable serif, soft contrast | Soft editorial, atmospheric |
| **Erode** | Fontshare | Distressed serif, hand-set feel | Riso, tactile-rebellion, brand-y |
| **Tanker** | Fontshare | Heavy condensed grotesque, pure display | One-word posters, mastheads |

### Free body faces

| Family | Source | Voice | Best for |
| --- | --- | --- | --- |
| **Geist** | Google | The default modern body sans | Modern minimal, SaaS, atmospheric |
| **Newsreader** | Google | Reading serif, optical-size aware | Editorial body, longform |
| **Source Serif 4** | Google | Body-grade serif | Editorial mid-weight |
| **EB Garamond** | Google | Classical body | Editorial slow reading |
| **Spectral** | Google | Slab-ish serif, screen-tuned | Long-form on screen |
| **Lora** | Google | Calligraphic serif, body-grade | Body — sparingly (over-used; see §11) |
| **Crimson Pro** | Google | Old-style body, generous | Editorial slow body |
| **IBM Plex Sans** | Google | Engineering sans, broad family | Technical body |
| **Switzer** | Fontshare | Neutral sans body | SaaS body, restrained |
| **General Sans** | Fontshare | Geist-adjacent body | Modern minimal body |

(Upstream hallmark also lists its in-repo face here as the default workhorse; substitute *the project's chosen body workhorse*.)

### Free mono / outlier faces

| Family | Source | Voice | Best for |
| --- | --- | --- | --- |
| **Geist Mono** | Google | Geist's mono companion | Default mono, code, captions |
| **JetBrains Mono** | Google | Engineering mono, ligatures | Code, terminal, technical |
| **IBM Plex Mono** | Google | Engineering mono, broad family | Technical body-grade |
| **Commit Mono** | Google | Tighter mono, modern | Code, modern terminal |
| **Space Mono** | Google | Quirky, slightly retro | Playful tech, riso |

### Tone-based pairing patterns

Each tone gets two rows: a **free baseline** (Google Fonts / Fontshare; works out of the box) and a **paid upgrade** (foundry licences required; only when the user has confirmed the budget and the licence). The free row is the default. **Never name a paid font in code without confirming the user is licensed** — the demo will fall back to system-default and look broken to the user. <!-- rule:type-paid-font-licence -->

| Tone | Tier | Display | Body | Outlier |
| --- | --- | --- | --- | --- |
| **Editorial** | Free | Fraunces · Newsreader · EB Garamond · Instrument Serif · Cabinet Grotesk | IBM Plex Sans · Switzer · Source Serif 4 | JetBrains Mono · Geist Mono · Erode (display moment) |
| | *Paid* | *Tiempos Headline · Söhne Breit · Reckless Display · Migra · Tobias* | *Söhne · Haffer · Untitled Sans* | *Söhne Mono · GT America Mono* |
| **Technical** | Free | JetBrains Mono · Geist Mono · Geist (700) · Commit Mono | Geist · IBM Plex Sans · Switzer | Tomorrow · Cabinet Grotesk (wordmark) |
| | *Paid* | *Berkeley Mono · Söhne Mono · GT Pressura · ABC Diatype Mono* | *Söhne · Untitled Sans · ABC Diatype* | *Berkeley Mono · GT Pressura Mono* |
| **Brutalist** | Free | Bricolage Grotesque (800) · Anton · Tanker · Big Shoulders Display | Geist · Switzer | Space Grotesk (numerals) · Geist Mono |
| | *Paid* | *Druk · Monument Extended · NaN Jaune · Migra · ABC Pressura* | *Söhne Breit · GT America* | *GT America Mono* |
| **Soft** | Free | Geist · Bricolage Grotesque (500) · Sentient · Newsreader | Geist · Crimson Pro · Switzer | Geist Mono · Satoshi (label) |
| | *Paid* | *Söhne · GT Pressura · Pangaia · Tobias* | *Söhne · Halyard Text · Satoshi* | *Söhne Mono · GT Maru Mono* |
| **Luxury** | Free | Cormorant Garamond · Fraunces · Cardo · DM Serif Display · Bodoni Moda | EB Garamond · Crimson Pro · Source Serif 4 | (rare; small caps from display family) |
| | *Paid* | *Canela · Tiempos Headline · GT Super · Domaine Display · Migra* | *Tiempos Text · Suisse Int'l · Domaine Text* | *(rarely used at this tier)* |
| **Playful** | Free | Bricolage Grotesque · Fraunces (italic) · Satoshi · Newsreader (italic) · Sentient | Geist · Newsreader · Satoshi | Geist Mono · Space Mono |
| | *Paid* | *Clash Display · Cabinet Grotesk · Migra · Tobias · Pangaia* | *Satoshi · Plus Jakarta Sans · GT Maru* | *Space Mono · GT Maru Mono* |
| **Austere** | Free | system-ui · Inter Tight (regular) · Geist (400) · Switzer (regular) | system-ui · Geist · Switzer | system-ui mono · Geist Mono |
| | *Paid* | *ABC Diatype · ABC Monument Grotesk · Söhne (regular) · ABC Pressura* | *ABC Diatype · Söhne* | *ABC Diatype Mono · Söhne Mono* |
| **Atmospheric** | Free | Geist (600) · Sentient · Tomorrow · Bricolage Grotesque | Geist (400) · Switzer | Geist Mono · JetBrains Mono |
| | *Paid* | *Söhne · GT Pressura · ABC Diatype* | *Söhne · ABC Diatype* | *Berkeley Mono · Söhne Mono* |
| **Workshop** *(upstream hallmark's own theme)* | Free | the project's chosen body workhorse · Geist · Cabinet Grotesk | the project's chosen body workhorse · Switzer | its mono companion · Geist Mono |
| | *Paid* | *Avenir Next · GT Walsheim* | *Söhne · GT Walsheim* | *Berkeley Mono* |

**The discipline.** Default to the free pairings. They're not consolation prizes; Fraunces, Geist, Bricolage Grotesque, Cabinet Grotesk, Sentient, and JetBrains Mono are first-rate faces in 2026. The paid upgrades exist for two cases: (a) the user has explicitly confirmed they're licensed, or (b) the user is asking for a specific named foundry voice (e.g., "make it look like Klim", "I want Söhne"). Reach for Tier 2 only then; otherwise the free row is the right answer. Treat the free row as canon, the paid row as a *cited* alternative.

**Pairing beyond this table.** When pairing outside the tone table, contrast on a real axis — structure (serif + sans), personality (geometric + humanist), or proportion (condensed display + wide body) — and never pair fonts that are similar but not identical (two geometric sans-serifs). You often don't need a second font at all: one well-chosen family in multiple weights creates cleaner hierarchy than two competing typefaces. Generic pairing catalogues (57 curated pairings and the like) are owned by the `ui-ux-pro-max` plugin skill — consult it rather than restating pairing data here. <!-- rule:type-pairing-contrast-axis -->

## Wordmark / logo typography

The wordmark in the navbar and footer **may use a different display face than the body**. On tone-rich themes (Editorial, Atelier, Specimen) it **should** — collapsing the wordmark into the body family flattens the visual hierarchy and the page reads as un-branded.

```css
:root {
  --display:       "Geist", system-ui, sans-serif;     /* body + display */
  --font-wordmark: "Fraunces", Georgia, serif;         /* logo only */
}
.wordmark {
  font-family: var(--font-wordmark);
  font-weight: 600;
  letter-spacing: -0.015em;
}
```

When to use the same family for both:

- **Editorial · Letter · Manifesto · Long Document** can collapse to a single family because the body voice carries the brand. The wordmark in these contexts is small, grounded, and earns its weight by being typeset rather than decorated.

When to use a contrasting family:

- **Bento Grid · Stat-Led · Workbench · Marquee Hero** — these archetypes lean visually generic (geometric grids, big numbers, browser-frame mockups) and need the wordmark to do the typographic differentiation work the body can't.

**Avoid the same-family collapse on a SaaS page.** A Geist-only page where the wordmark is also Geist 600 reads as un-designed; the wordmark in Fraunces SemiBold over a Geist body costs nothing and adds the one typographic register that says *this is a brand*. <!-- rule:type-wordmark-register -->

(Specific wordmark-pairing suggestions are generic pairing data — consult the `ui-ux-pro-max` plugin's pairing catalog; the doctrine above is what this file owns.)

## Scale

Pick a ratio. The default is **1.25** (major third). Build the scale from a 16px body, then clamp display sizes for responsive (brand register only — see § Register).

```css
:root {
  --text-xs:   0.64rem;   /* 10.24px */
  --text-sm:   0.8rem;    /* 12.8px  */
  --text-base: 1rem;      /* 16px    */
  --text-md:   1.25rem;   /* 20px    */
  --text-lg:   1.5625rem; /* 25px    */
  --text-xl:   1.9531rem; /* 31.25px */
  --text-2xl:  2.4414rem;
  --text-3xl:  3.0518rem;
  --text-4xl:  3.8147rem;
  --text-display: clamp(2.75rem, 5vw + 1rem, 5.25rem);
}
```

**Display max — keep it ≤ 5.5rem (88 px).** Above that, hero headlines crowd themselves on 1280–1440 px viewports and require multi-line wrapping that almost always reads as drama, not gravity. Even on Manifesto / Brutal display-heavy themes, cap at 6rem (96 px). The exception is a single-line, single-word display (e.g. a stat) that occupies ≤ 12 ch — it can grow to 7rem. **Default emit format is `clamp(2.75rem, 5vw + 1rem, 5.25rem)`.** <!-- rule:type-display-max -->

### Hero headline sizing — match size to copy length

Count characters in the rendered hero `h1`. Pick the cap by bucket — the rule applies on top of any per-theme `--text-display` clamp: <!-- rule:type-hero-size-by-char-count -->

| Headline length | Size cap | Notes |
| --- | --- | --- |
| **≤ 20 chars** (e.g. *"Limitless"*, *"Made not generated"*) | full `--text-display`; single-word can grow to 7rem | Display-heavy themes only |
| **21–50 chars** (the default sweet spot) | `--text-display` | If it wraps past 2 lines at 414 px, step down to `--text-display-s` |
| **51–90 chars** | cap at `--text-display-s` | Strongly consider splitting into eyebrow + headline |
| **> 90 chars** | rewrite shorter, or cap at `--text-4xl` with tighter leading | A 100-char headline at display size is the single most reliable AI tell |

**Aggressive-display themes step down one rung when headline > 50 chars.** Brutal, Riso, and Manifesto clamp `--text-display` at 6.5–9rem — that ceiling is for ≤ 50-char statements only. Past 50 chars, route them to `--text-display-s` automatically. **When you write the headline yourself (no user-supplied copy), aim for ≤ 7 words and ≤ 50 chars from the start** — imperative or nominal phrase, never a gerund opener.

Use no more than five sizes on a single page. If you need more hierarchy, use weight and colour, not another size.

## Weights

- Body: one weight (typically 400 or 350). Bold for emphasis only.
- Headings: a weight that contrasts the body by at least 300 units. If body is 400, headings are 700 or 200 — not 500 or 600.
- Define clear roles for each weight and stick to them — not bold in one section, semibold in another for the same role. Don't use more than 3–4 weights (Regular, Medium, Semibold, Bold is plenty). <!-- rule:type-weight-roles -->
- Load only the weights you actually use (each weight adds to page load).
- Never synthesise. Load the weight you need; don't rely on `font-weight: bold` against a single-weight file.

## Web font loading

The layout-shift problem: fonts load late, text reflows, users see content jump. The fix:

```css
/* 1. Use font-display: swap for visibility */
@font-face {
  font-family: 'CustomFont';
  src: url('font.woff2') format('woff2');
  font-display: swap;
}

/* 2. Match fallback metrics to minimize shift */
@font-face {
  font-family: 'CustomFont-Fallback';
  src: local('Arial');
  size-adjust: 105%;        /* Scale to match x-height */
  ascent-override: 90%;     /* Match ascender height */
  descent-override: 20%;    /* Match descender depth */
  line-gap-override: 10%;   /* Match line spacing */
}

body {
  font-family: 'CustomFont', 'CustomFont-Fallback', sans-serif;
}
```

Tools like [Fontaine](https://github.com/unjs/fontaine) calculate these overrides automatically. `font-display: swap` + metric-matched fallbacks (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) are required on every web font. <!-- rule:type-metric-matched-fallback -->

**`swap` vs `optional`**: `swap` shows fallback text immediately and FOUT-swaps when the web font arrives. `optional` uses the fallback if the web font misses a small load budget (~100ms) and avoids the shift entirely. Pick `optional` when zero layout shift matters more than seeing the branded font on slow networks. <!-- rule:type-swap-vs-optional -->

**Preload the critical weight only**: typically the regular-weight body font used above the fold. Preloading every weight costs more bandwidth than it saves.

**Variable fonts for 3+ weights or styles**: a single variable font file is usually smaller than three static weight files, gives fractional weight control, and pairs well with `font-optical-sizing: auto`. For 1–2 weights, static is fine.

## Rendering polish and OpenType features

- Tabular numbers on any data display: `font-variant-numeric: tabular-nums;`.
- Oldstyle figures for body copy where the face supports them: `font-variant-numeric: oldstyle-nums;`.
- Proper fractions: `font-variant-numeric: diagonal-fractions;`. Small caps for abbreviations: `font-variant-caps: all-small-caps;`. Disable ligatures in code: `code { font-variant-ligatures: none; }`. Be explicit about kerning: `font-kerning: normal;`. Variable fonts: `font-optical-sizing: auto;` picks the right optical-size master automatically. Check what features a font supports at [Wakamai Fondue](https://wakamaifondue.com/).
- **ALL-CAPS tracking: capitals sit too close at default spacing. Add 5–12% letter-spacing (`letter-spacing: 0.05em` to `0.12em`) to short all-caps labels, eyebrows, and small headings.** Real small caps (via `font-variant-caps`) need the same treatment, slightly gentler. <!-- rule:type-caps-tracking -->
- Proper typographic punctuation: `" " — … ' '`. Never straight quotes, never `--` or `...`.
- Name tokens semantically (`--text-body`, `--text-heading`), not by value (`--font-size-16`). Include font stacks, size scale, weights, line-heights, and letter-spacing in the token system.

## Body text rules

- Minimum 16px. Below 14px is accessibility-hostile.
- Line-height 1.5–1.65 on body copy, tighter (1.1–1.3) on display. **Floor for all-caps display heads (`text-transform: uppercase` on `.hero__display` / `.section__title` / `h1` / `h2`) is `1.0` — recommended `1.02–1.08`.** Below 1.0 the cap-tops of line N+1 collide with the baseline of line N (no descenders to cushion the gap); the comma + cap-D on a wrapped "PROMPT, / DIFFERENT" fuse into a single glyph blob. Condensed display faces make this worse. The design-review slop gates auto-fail the pattern (`departments/brand/skills/design-review/` — upstream: hallmark gate 55). <!-- rule:type-allcaps-leading-floor -->
- Measure 45–75 characters (`max-width: 65ch`). Line-height scales inversely with line length: narrow columns need tighter leading, wide columns need more.
- **Light-on-dark compensation is three axes, not one.** Light text on dark backgrounds: bump line-height by 0.05–0.1, add a touch of letter-spacing (0.01–0.02em), and optionally step the body weight up one notch (regular → medium). The perceived weight drops across all three axes; fix all three. <!-- rule:type-dark-bg-three-axis -->
- **Paragraph rhythm**: pick either space between paragraphs OR first-line indentation. Never both. Digital usually wants space; editorial/long-form can justify indent-only.
- Never all-caps body copy. Never justified text without hyphenation. Never letter-spacing above 0.05em on body.

## Headings rules

- Tight tracking on display sizes (`letter-spacing: -0.02em` to `-0.04em` depending on the face).
- Loose tracking on small caps / labels (`letter-spacing: 0.08em` to `0.14em`, `text-transform: uppercase`, use small caps if the face has them: `font-variant-caps: all-small-caps;`).
- Skip no levels. `h1` → `h2` → `h3`. Style them visually how you like, but keep semantic order.

## Vertical rhythm

Line-height is the base unit for ALL vertical spacing. If body text has `line-height: 1.5` on `16px` type (= 24px), spacing values should be multiples of 24px. This creates subconscious harmony; text and space share a mathematical foundation. <!-- rule:type-vertical-rhythm -->

## Accessibility

- **Never disable zoom**: `user-scalable=no` breaks accessibility. If the layout breaks at 200% zoom, fix the layout. <!-- rule:type-never-disable-zoom -->
- **Use rem/em for font sizes** — respects user browser settings. Never `px` for body text.
- **Minimum 16px body text** — smaller strains eyes and fails WCAG on mobile.
- **Adequate touch targets**: text links need padding or line-height that creates 44px+ tap targets.
- Text must meet WCAG contrast ratios (see the contrast discipline in [`interaction-states.md`](interaction-states.md)).

## Bans

- Reflex-default faces: see the canonical list in `departments/brand/references/uiux-knowledge-and-tools.md` §11. No system stack as the *only* stack on brand surfaces.
- No gradient text on headings (`background-clip: text` with a gradient fill).
- No single-font pages (unless the single font IS the design choice — see Principles).
- No decorative/display fonts for body text.
- No all-caps paragraphs.
- No font-size below 14px for body copy, below 10px anywhere.
- No hard-synthesised bold or italic.
- No arbitrary sizes — commit to a scale.
- No skipped fallback font definitions; no ignoring font-loading performance (FOUT/FOIT).
- **No more than three font families on a single page.** Display + body + one outlier is the ceiling. Four families = slop. Audit gate.
- No outlier face used in more than two slots. Wordmark + hero stat is the canonical pair; if you reach for a third slot, drop it back to the body face.
