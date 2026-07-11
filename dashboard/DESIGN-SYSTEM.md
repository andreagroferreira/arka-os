# ArkaOS Pulse — Dashboard Design System

> v1 · Phase 0 of the dashboard UI reform. Reference page: `/design-lab`.
> Benchmark discipline: Vercel (dark restraint) · Linear (density, speed) ·
> Framer (motion as language). Concept DNA: Jarvis — the dashboard reads as
> a *living system*, never as a sci-fi prop.

## Principles

1. **Green means alive.** `arka` green is reserved for live data, primary
   actions, and health. It is never decoration. If everything glows,
   nothing does.
2. **Dark is the flagship.** Light mode is a first-class derivative with
   its own contrast decisions (never inverted values).
3. **Surfaces are carbon, not black.** Every dark surface carries a green
   undertone (`carbon` scale). Flat `#000` is banned.
4. **Numbers are data.** All metrics render in mono with
   `tabular-nums` (`.arka-data`) so ticking values never shift layout.
5. **One rhythm.** All motion uses the shared duration/easing tokens.
   Only genuinely live elements may pulse. `prefers-reduced-motion`
   disables all ambient animation.

## Tokens (source: `app/assets/css/main.css`)

### Color

| Scale | Anchor | Role |
|---|---|---|
| `arka` | 400 = `#00FF88` (brand) | Signal green — primary, live, success |
| `carbon` | 950 = `#0A0D0B` | Green-tinted neutrals — all surfaces/text |

Semantic mapping via Nuxt UI: `primary: 'arka'`, `neutral: 'carbon'`
(`app/app.config.ts`). Dark primary resolves to `arka-400`; light primary
darkens to `arka-700` for contrast on paper. `warning`/`error`/`info` stay
on Nuxt UI defaults; `info` (cyan) is the secondary data voice in charts.

### Surfaces (dark)

`--ui-bg #070908` (void) → `--ui-bg-muted #0C100E` → `--ui-bg-elevated
carbon-950` → `--ui-bg-accented carbon-900`. Borders `#1E2521`/`#151A17`.

### Typography

| Role | Face | Usage |
|---|---|---|
| Display | Space Grotesk | Headings, `font-display` |
| Body | Inter | UI text, `font-sans` |
| Data | JetBrains Mono | Numbers, IDs, statuses, eyebrows — `font-mono` |

Loaded via `@nuxt/fonts`. Type scale: 36/24/18/16/14/12.

### Motion

| Token | Value |
|---|---|
| `--arka-motion-fast/base/slow` | 150ms / 240ms / 400ms |
| `--arka-ease-out` (enter) | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `--arka-ease-in` (exit, ~65% of enter) | `cubic-bezier(0.7, 0, 0.84, 0)` |
| `--arka-pulse-period` | 2.4s |
| `--arka-stagger-step` | 40ms |

## Vocabulary (utilities)

| Class | Meaning |
|---|---|
| `.arka-eyebrow` | HUD label: mono, uppercase, tracked, signal tick |
| `.arka-live-dot` | Breathing dot — genuinely live data only |
| `.arka-pulse-line` | Signature EKG sweep — max one per view |
| `.arka-stream-in` | Entry animation for arriving live content |
| `.arka-data` | Tabular mono for metrics |

## Rules for page waves (Phases 1+)

- No hardcoded colors in components — semantic tokens only.
- Charts (unovis) take their palette from tokens; load the `dataviz`
  skill before building any chart.
- Hero motion moments may add GSAP *per page wave*, on the shared rhythm
  tokens; ambient/micro motion stays CSS.
- Every wave passes: Valentina visual validation → Playwright evidence
  (dark + light) → Quality Gate.
