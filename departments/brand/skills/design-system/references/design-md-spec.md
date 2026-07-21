# design.md — portable design-system spec + exports

> Source: merge of `references/design-md.md` + `references/export-formats.md` from the **hallmark** skill repo (MIT — see `hallmark.LICENSE` in this references directory). Adapted for ArkaOS; an ArkaOS bridge paragraph closes the file.

`design.md` is the opt-in portable design system: loaded ONLY when the user explicitly asks to lock the current build's design system into a portable file. The default build flow does NOT auto-emit `design.md`. The user iterates freely until they say the system is settled, then asks for it.

This spec is **also** used by [`design-dna-study.md`](design-dna-study.md) when the user — after a successful `study` diagnosis — asks for the DNA to be emitted as a portable system. The format below is shared between the two paths; the only differences are spelled out in § Two emission paths (default vs study) and in [`design-dna-study.md`](design-dna-study.md) § Emitting a `design.md` from `study`.

## Triggers (phrase-only — no new verb)

Fire ONLY when the user says one of:

- *"lock the system"* / *"lock the design system"* / *"lock the DNA"* / *"lock this DNA"*
- *"give me a design.md"* / *"write a design.md"* / *"export this as a design.md"*
- *"extract this to a design system"* / *"extract the tokens"* / *"extract the DNA"*
- *"make this portable"* / *"make the DNA portable"*
- *"I want to use this in another project"*

For everything else — including the default build, a redesign of a single page, and free iteration on the same brief — skip. Single-page work stays token-portable via `tokens.css`; `design.md` is the explicit lock-in step.

## Two emission paths (default vs study)

The same `design.md` format is emitted from two different entry points. They differ in which signals seed the file and in how strict the refusal layer is.

| | **Default-build path** (lock the system) | **Study path** (lock the DNA) |
| --- | --- | --- |
| **Trigger context** | After at least one build the user has iterated on and is satisfied with | After a successful `study` diagnosis (image or URL) |
| **Source of tokens** | The build's in-memory token state | The studied DNA — exact from CSS in URL mode, estimated from bands in image mode |
| **Refusal layer** | None — the user owns the build they iterated on | Tighter — see [`design-dna-study.md`](design-dna-study.md) § Emission-refusal layer. URL mode requires attestation; third-party URLs are refused |
| **`## Provenance` block** | Omitted (the system is the user's own work) | Required — records source mode, URL or "image", date, attestation answer, confidence note |
| **`## Notes` block** | Optional — covers any decisions worth remembering | Required — carries the diagnosis's "anti-patterns to NOT carry over" list |

Both paths produce a `design.md` that subsequent runs can read; the file format is uniform once written.

## Scope

- **Page-builds only.** Skip on component-scope — a single component is too small to be a system.
- **Multi-page redesign keeps existing behaviour.** A multi-page redesign produces the heavyweight `design.md` as part of its own flow (upstream: `verbs/redesign.md` § Multi-page flow — unported). That flow already implies a locked system, so the rule there is unchanged.
- **No-overwrite policy.** If `design.md` already exists at the project root, do NOT overwrite. Refresh its `## Exports` section instead and emit one line: *"design.md detected — refreshed Exports, system unchanged."*

## CTA — surface the offer in the build preview

After every default + redesign page-build, append one quiet line at the bottom of the preview block:

> *System portable? Say `lock the system` to extract this build's tokens + voice into a `design.md`.*

Skip the CTA when (a) the build is component-scope, or (b) `design.md` already exists in the project (system is already locked).

## Format (the tight version)

Write the file at the project root. Match the project's case convention (`design.md` or `DESIGN.md`). Target ~45 lines — enough to seed a real app, not so much that it becomes a wiki to maintain. The format:

````markdown
# Design — <Project name>

Locked design system. Future runs read this file first; pages defer
to it. Amend intentionally — the file is the rule.

## System
- Genre · <editorial / modern-minimal / atmospheric / playful>
- Macrostructure · <name>
- Theme · <catalog: NAME · or · custom (vibe: "<4–8 words>")>
- Axes · <paper-band> / <display-style> / <accent-hue>

## Tokens (canonical · `tokens.css` is the source of truth)
```css
:root {
  --color-paper:      oklch(<L> <C> <H>);
  --color-paper-2:    oklch(<L> <C> <H>);
  --color-ink:        oklch(<L> <C> <H>);
  --color-ink-2:      oklch(<L> <C> <H>);
  --color-rule:       oklch(<L> <C> <H>);
  --color-accent:     oklch(<L> <C> <H>);
  --color-accent-ink: oklch(<L> <C> <H>);
  --color-focus:      oklch(<L> <C> <H>);

  --font-display: "<face>", ...;
  --font-body:    "<face>", ...;
  --font-mono:    "<face>", ...;

  /* 4-pt spacing scale, named: --space-3xs … --space-4xl. See tokens.css.   */
  /* Type scale, 1.25 (major-third) ratio: --text-xs … --text-display.       */

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-fast: 180ms;  --dur-base: 240ms;  --dur-slow: 320ms;

  --radius-card: <px>;  --radius-pill: <px>;  --radius-input: <px>;
}
```

## CTA voice
- Primary · <fill colour> · <radius> · <padding rhythm>
- Secondary · <outline / ghost> · <same radius>

## Motion stance
- <silent · 1–2 reveal primitives · motion-cut>
- Reduced-motion fallback · ≤150 ms opacity crossfade.

## Exports
`tokens.css` (in this project) is the source of truth. For Tailwind v4
`@theme`, DTCG `tokens.json`, or shadcn/ui CSS variables, ask *"extend
design.md with Tailwind exports"* (or the format you want) — they will
be appended per § Export formats below.
````

State the picks aloud BEFORE writing the file. *"Genre: editorial. Macrostructure: Long Document. Theme: catalog Editorial. Locking this as the project's system."* Then write.

## After the file is written

Once `design.md` exists, the pre-flight scan detects it on every subsequent run. From that point on:

- All future runs READ `design.md` first; subsequent picks (genre / theme / typography / motion / CTA voice) defer to it.
- The diversification rule INVERTS — pages must SHARE the system, not differ from each other.
- If a future page genuinely needs a different system, AMEND `design.md` with a `## Variants` section rather than overriding locally — the file evolves; per-page overrides do not.

## Why opt-in (not auto-emit)

Briefs iterate. The first build is rarely the settled design. Auto-emitting `design.md` on every default build would either churn the file across iterations or lock a weak system before the user has reviewed it. Opt-in mirrors how design teams actually work — formalise the system after the patterns hold, not on day one. The CTA in the preview block keeps the feature discoverable without forcing it.

---

# Export formats

Loaded when emitting the design system as portable tokens. Defines the four canonical formats every emission writes:

1. **`tokens.css`** — the source of truth. Always emitted alongside the page CSS.
2. **Tailwind v4 `@theme`** — for projects on Tailwind. Emitted into `design.md`'s Exports section on multi-page projects.
3. **DTCG `tokens.json`** — for projects using a token pipeline (Style Dictionary, Token Studio, Cobalt). Emitted into `design.md`.
4. **shadcn/ui CSS variables** — for projects using shadcn/ui's component library. Emitted into `design.md`.

The output rule: `tokens.css` is always written. The other three live inline in `design.md` so the user copies whichever they need into a new project. **No new verb.** This is a side effect of every build.

---

## Token taxonomy — the source of truth

Every build writes these tokens (or a subset, if the page doesn't use one). The names are the source; every other format is a translation.

| Token | Type | Example value |
| --- | --- | --- |
| `--color-paper` | colour | `oklch(96% 0.018 80)` |
| `--color-paper-2` | colour | `oklch(94% 0.020 80)` |
| `--color-paper-3` | colour | `oklch(91% 0.022 80)` |
| `--color-ink` | colour | `oklch(15% 0.012 80)` |
| `--color-ink-2` | colour | `oklch(28% 0.014 80)` |
| `--color-rule` | colour | `oklch(86% 0.018 80)` |
| `--color-rule-2` | colour | `oklch(72% 0.020 80)` |
| `--color-muted` | colour | `oklch(50% 0.014 80)` |
| `--color-neutral` | colour | `oklch(38% 0.012 80)` |
| `--color-accent` | colour | `oklch(58% 0.16 70)` |
| `--color-accent-ink` | colour | (text on accent fill, ≥ APCA 7:1) |
| `--color-focus` | colour | (often = accent at higher chroma) |
| `--font-display` | font | `"Fraunces", ui-serif, Georgia, serif` |
| `--font-body` | font | `"Geist", ui-sans-serif, system-ui, sans-serif` |
| `--font-outlier` | font | `"Geist Mono", ui-monospace, monospace` |
| `--space-3xs` … `--space-5xl` | length | 4-pt scale: `0.25rem` … `8rem` |
| `--text-xs` … `--text-display` | length | 1.25 (major-third) ratio scale |
| `--ease-out` / `--ease-in` / `--ease-in-out` | easing | `cubic-bezier(0.16, 1, 0.3, 1)` etc. |
| `--dur-micro` / `--dur-short` / `--dur-long` | time | `120ms` / `220ms` / `420ms` |
| `--rule-hair` / `--rule-fine` | length | `1px` / `2px` |
| `--radius-card` / `--radius-pill` / `--radius-input` | length | varies per theme |
| `--shadow-card` | shadow | varies per theme |

If the page introduces *additional* tokens, name them by role and add to `tokens.css`. Don't make up token names downstream that aren't in `tokens.css` — the source of truth is the source of truth.

---

## Format 1 — `tokens.css`

The source. Plain CSS custom properties at `:root`. Every page CSS imports this file at the top:

```css
@import "tokens.css";
/* page CSS continues — uses var(--color-paper), never raw values */
```

Or, if the project uses a CSS bundler / framework that doesn't honour bare `@import`, the project's existing entry-point imports `tokens.css` before the page CSS that consumes it (keep it among the other top-of-file `@import`s, never above or in place of `@import "tailwindcss"`). The page CSS still references tokens by name, never by raw value.

**Worked example — editorial theme (Specimen-like):**

```css
:root {
  --color-paper:        oklch(96% 0.018 80);
  --color-paper-2:      oklch(94% 0.020 80);
  --color-paper-3:      oklch(91% 0.022 80);
  --color-rule:         oklch(86% 0.020 78);
  --color-rule-2:       oklch(72% 0.022 78);
  --color-muted:        oklch(50% 0.018 78);
  --color-neutral:      oklch(38% 0.014 76);
  --color-ink-2:        oklch(28% 0.012 75);
  --color-ink:          oklch(15% 0.010 75);
  --color-accent:       oklch(58% 0.16 60);
  --color-accent-ink:   oklch(98% 0.012 75);
  --color-focus:        oklch(58% 0.16 60);

  --font-display: "Fraunces", "Cardo", ui-serif, Georgia, serif;
  --font-body:    "Geist", "Söhne", ui-sans-serif, system-ui, sans-serif;
  --font-outlier: "Geist Mono", "JetBrains Mono", ui-monospace, monospace;

  --display-weight: 400;
  --display-style:  italic;
  --tracking-display: -0.02em;
  --tracking-label:   0.10em;

  --text-xs:      0.75rem;
  --text-sm:      0.875rem;
  --text-md:      1.125rem;
  --text-lg:      1.375rem;
  --text-xl:      1.75rem;
  --text-2xl:     2.25rem;
  --text-display: clamp(3rem, 6vw + 1rem, 6.5rem);

  --space-3xs: 0.25rem;
  --space-2xs: 0.5rem;
  --space-xs:  0.75rem;
  --space-sm:  1rem;
  --space-md:  1.5rem;
  --space-lg:  2rem;
  --space-xl:  3rem;
  --space-2xl: 4.5rem;
  --space-3xl: 7rem;
  --space-4xl: 11rem;

  --rule-hair: 0.5px;
  --rule-fine: 1px;
  --radius-card:  0;
  --radius-pill:  0;
  --radius-input: 0;

  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in:     cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);

  --dur-micro: 120ms;
  --dur-short: 220ms;
  --dur-long:  420ms;
}
```

**Worked example — modern-minimal theme (austere, pure-white):**

```css
:root {
  --color-paper:      oklch(100%  0     0);
  --color-paper-2:    oklch(98.5% 0     0);
  --color-paper-3:    oklch(96%   0     0);
  --color-rule:       oklch(91%   0     0);
  --color-rule-2:     oklch(82%   0     0);
  --color-muted:      oklch(55%   0     0);
  --color-neutral:    oklch(40%   0     0);
  --color-ink-2:      oklch(28%   0     0);
  --color-ink:        oklch(15%   0     0);
  --color-accent:     oklch(15%   0     0);
  --color-accent-ink: oklch(100%  0     0);
  --color-focus:      oklch(60%   0.10  240);

  --font-display: "Geist", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-body:    "Geist", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-outlier: "Geist Mono", ui-monospace, "SF Mono", Menlo, monospace;

  --display-weight: 600;
  --display-style:  normal;
  --tracking-display: -0.025em;

  --radius-card:  8px;
  --radius-pill:  999px;
  --radius-input: 8px;
}
```

---

## Format 2 — Tailwind v4 `@theme`

Tailwind v4 reads CSS variables inside `@theme` and generates utilities (`bg-paper`, `text-ink`, etc.) automatically. The translation from the canonical tokens is direct — same variable names, same OKLCH values:

```css
@theme {
  /* Colours */
  --color-paper:        oklch(96% 0.018 80);
  --color-paper-2:      oklch(94% 0.020 80);
  --color-paper-3:      oklch(91% 0.022 80);
  --color-rule:         oklch(86% 0.020 78);
  --color-rule-2:       oklch(72% 0.022 78);
  --color-muted:        oklch(50% 0.018 78);
  --color-neutral:      oklch(38% 0.014 76);
  --color-ink-2:        oklch(28% 0.012 75);
  --color-ink:          oklch(15% 0.010 75);
  --color-accent:       oklch(58% 0.16 60);
  --color-focus:        oklch(58% 0.16 60);

  /* Fonts */
  --font-display: "Fraunces", "Cardo", ui-serif, Georgia, serif;
  --font-body:    "Geist", ui-sans-serif, system-ui, sans-serif;
  --font-outlier: "Geist Mono", ui-monospace, monospace;

  /* Spacing — Tailwind reads --spacing-* by default; we keep the --space-* names alongside */
  --spacing-3xs: 0.25rem;
  --spacing-2xs: 0.5rem;
  --spacing-xs:  0.75rem;
  --spacing-sm:  1rem;
  --spacing-md:  1.5rem;
  --spacing-lg:  2rem;
  --spacing-xl:  3rem;
  --spacing-2xl: 4.5rem;

  /* Type scale — Tailwind reads --text-* */
  --text-xs:      0.75rem;
  --text-sm:      0.875rem;
  --text-md:      1.125rem;
  --text-lg:      1.375rem;
  --text-xl:      1.75rem;
  --text-2xl:     2.25rem;

  /* Radius */
  --radius-card:  0;
  --radius-pill:  0;
  --radius-input: 0;

  /* Easings — Tailwind reads --ease-* */
  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in:     cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}
```

Notes:
- Tailwind v4 expects `--spacing-*` (with `ing`) for the spacing utilities. We mirror `--space-*` to `--spacing-*` so both names work.
- `--text-*` works as-is (Tailwind v4 picks them up for `text-md` etc.).
- `--font-*` becomes `font-display` / `font-body` / `font-outlier` utilities.
- The user's `tailwind.config.{ts,js}` may need `@source` directives but no `theme.extend` — v4 reads `@theme` directly.

---

## Format 3 — DTCG `tokens.json`

W3C Design Tokens Community Group format. For projects using Style Dictionary, Cobalt, or Token Studio. Path-based; OKLCH stays as a string value; `$type` is required.

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "paper":   { "$value": "oklch(96% 0.018 80)", "$type": "color" },
    "paper-2": { "$value": "oklch(94% 0.020 80)", "$type": "color" },
    "paper-3": { "$value": "oklch(91% 0.022 80)", "$type": "color" },
    "rule":    { "$value": "oklch(86% 0.020 78)", "$type": "color" },
    "rule-2":  { "$value": "oklch(72% 0.022 78)", "$type": "color" },
    "muted":   { "$value": "oklch(50% 0.018 78)", "$type": "color" },
    "neutral": { "$value": "oklch(38% 0.014 76)", "$type": "color" },
    "ink-2":   { "$value": "oklch(28% 0.012 75)", "$type": "color" },
    "ink":     { "$value": "oklch(15% 0.010 75)", "$type": "color" },
    "accent":  { "$value": "oklch(58% 0.16 60)",  "$type": "color" },
    "focus":   { "$value": "oklch(58% 0.16 60)",  "$type": "color" }
  },
  "font": {
    "display": { "$value": "Fraunces, Cardo, ui-serif, Georgia, serif", "$type": "fontFamily" },
    "body":    { "$value": "Geist, ui-sans-serif, system-ui, sans-serif", "$type": "fontFamily" },
    "outlier": { "$value": "Geist Mono, ui-monospace, monospace",         "$type": "fontFamily" }
  },
  "size": {
    "text-xs":      { "$value": "0.75rem",  "$type": "dimension" },
    "text-sm":      { "$value": "0.875rem", "$type": "dimension" },
    "text-md":      { "$value": "1.125rem", "$type": "dimension" },
    "text-lg":      { "$value": "1.375rem", "$type": "dimension" },
    "text-xl":      { "$value": "1.75rem",  "$type": "dimension" },
    "text-2xl":     { "$value": "2.25rem",  "$type": "dimension" },
    "text-display": { "$value": "6rem",     "$type": "dimension" }
  },
  "space": {
    "3xs": { "$value": "0.25rem", "$type": "dimension" },
    "2xs": { "$value": "0.5rem",  "$type": "dimension" },
    "xs":  { "$value": "0.75rem", "$type": "dimension" },
    "sm":  { "$value": "1rem",    "$type": "dimension" },
    "md":  { "$value": "1.5rem",  "$type": "dimension" },
    "lg":  { "$value": "2rem",    "$type": "dimension" },
    "xl":  { "$value": "3rem",    "$type": "dimension" },
    "2xl": { "$value": "4.5rem",  "$type": "dimension" },
    "3xl": { "$value": "7rem",    "$type": "dimension" },
    "4xl": { "$value": "11rem",   "$type": "dimension" }
  },
  "duration": {
    "micro": { "$value": "120ms", "$type": "duration" },
    "short": { "$value": "220ms", "$type": "duration" },
    "long":  { "$value": "420ms", "$type": "duration" }
  }
}
```

Notes:
- DTCG accepts `oklch(...)` strings on modern tooling. If the user's pipeline doesn't, convert to hex (lossy — flag this) or to `color(oklch ...)` (CSS Color 4).
- The `text-display` value uses a fixed `6rem` for portability — the responsive `clamp(...)` belongs in CSS, not in token JSON.

---

## Format 4 — shadcn/ui CSS variables

shadcn/ui's component library reads CSS custom properties with specific names, in a specific shape. The values are **space-separated** triples (no `oklch()` wrapper, no commas) so shadcn can compose them with `oklch(<value> / <alpha>)`.

The translation from the canonical tokens:

```css
:root {
  --background:           96%   0.018 80;     /* paper */
  --foreground:           15%   0.010 75;     /* ink */

  --card:                 94%   0.020 80;     /* paper-2 */
  --card-foreground:      15%   0.010 75;     /* ink */

  --popover:              94%   0.020 80;     /* paper-2 */
  --popover-foreground:   15%   0.010 75;     /* ink */

  --primary:              58%   0.16  60;     /* accent */
  --primary-foreground:   98%   0.012 75;     /* accent-ink */

  --secondary:            91%   0.022 80;     /* paper-3 */
  --secondary-foreground: 28%   0.012 75;     /* ink-2 */

  --muted:                86%   0.020 78;     /* rule */
  --muted-foreground:     50%   0.018 78;     /* muted */

  --accent:               58%   0.16  60;     /* accent (same as primary in this taxonomy) */
  --accent-foreground:    98%   0.012 75;

  --destructive:          58%   0.20  25;     /* warm red, fixed */
  --destructive-foreground: 98% 0.012 75;

  --border:               86%   0.020 78;     /* rule */
  --input:                86%   0.020 78;     /* rule */
  --ring:                 58%   0.16  60;     /* focus */

  --radius:               0;                   /* radius-card; shadcn uses one value */
}
```

Then the user's `tailwind.config.ts` (or v4 `@theme`) reads them with `oklch(var(--background))`. The accent → shadcn's primary is the canonical mapping; secondary → paper-3.

If the user wants a dark variant, mirror with dark theme tokens under a `.dark` selector (a dark catalog theme — e.g. [lumen Night Foundry](themes/lumen.md) — supplies the values).

---

## Output rule

When emitting exports:

1. **Always** write `tokens.css` next to the page CSS (or in the project root for multi-file projects). Format 1.
2. **On `design.md`-managed projects** (multi-page), embed all four formats inline in `design.md`'s Exports section. The user copies whichever they need.
3. **On Tailwind projects** (detected at pre-flight), additionally surface the Tailwind `@theme` block in the build output so the user knows where to paste it (typically into `app/globals.css` or the equivalent).
4. **Merge into an existing entry stylesheet; never overwrite it.** When the target project already has `app/globals.css` (or `src/index.css`, `src/styles/global.css`): keep its existing `@import "tailwindcss"` / `@tailwind base|components|utilities` directives exactly as they are, append the `:root` tokens and base rules *after* them, and keep any `@import "tokens.css"` at the very top of the file (CSS parses `@import` only before other rules, so a misplaced one is silently dropped and your tokens vanish). If the project already defines brand tokens (`--background`, `--foreground`, a Tailwind `@theme`), map the roles onto those names rather than adding a parallel set, or scope the tokens under a wrapper class. Replace the file outright only when the user has asked for a full takeover.

Don't blanket-emit tokens.json or shadcn variables on single-page projects — the user can copy them out of `design.md` if they upgrade to a multi-page system.

---

ArkaOS bridge: when a project declares `design-system.yaml` (rule `design-system-locked`), mirror the emitted tokens into the token source named by the `[arka:design] tokens=` marker field; the per-project linter (`core.governance.design_system_lint`) stays advisory. The emitted file lives at the project root as `design.md`.
