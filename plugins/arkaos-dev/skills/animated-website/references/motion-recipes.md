# Motion Recipes — timing, easing, interaction patterns

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT —
> Copyright (c) 2026 Hallmark contributors) `references/microinteractions.md`
> + `references/motion.md` and [impeccable](https://github.com/pbakaus/impeccable)
> (Apache-2.0 — Copyright Paul Bakaus) `skill/reference/animate.md`.
> License texts at `departments/brand/skills/design-review/references/`
> (`hallmark.LICENSE`, `impeccable.LICENSE`, `impeccable.NOTICE`).

Timing/easing tokens are canonical in the doctrine hub §4
(`departments/brand/references/uiux-knowledge-and-tools.md`); this file
maps recipes onto them and adds craft depth. Where upstream guidance
conflicts with the hub §4 forbidden list (rotation/spin, bounce/elastic
on the logo, 3D/perspective, particles, morphing, color-cycling), **the
hub wins** — conflicts are noted inline.
<!-- rule:motion-hub-tokens-canonical -->

A microinteraction is one event with four parts: trigger → rules →
feedback → loops/modes (Saffer). Get any of those wrong and the interface
feels uncrafted. Ship them all right and the interface feels *made* —
even when nothing else is unusual.

**Register split:** on brand surfaces, motion is part of the voice — one
well-rehearsed entrance beats scattered micro-interactions. On product
surfaces, motion conveys state (feedback, reveal, loading, view
transitions) at 150–250ms; no page-load choreography — users are in a
task and won't wait for it. The saturated AI default is fade-and-rise
reveals on every scrolled section; that's a tell, not a choreography
(law: hub §12).

## Principles

- **Motion has intent or motion is cut.** Every animation must clarify,
  guide, or confirm. If you cannot name what a transition communicates,
  it is decoration. Decoration is slop. <!-- rule:motion-intent-or-cut -->
- **Silent success.** A successful action does *not* deserve a "Done!"
  toast. If the user sees the result, they don't need a confirmation.
  Reserve toasts for failures and for actions that hide their own effect.
  <!-- rule:motion-silent-success -->
- **Optimism with rollback.** Update the UI immediately on user action,
  send the request in the background; if it fails, animate the rollback
  and offer Undo. Round-trip latency is a perception killer.
  <!-- rule:motion-optimistic-rollback -->
- **Restraint, not restraint-as-personality.** This canon is not
  "no motion" — it is *the right motion in the right place*. A drag
  handle that springs into focus on grab is good. A page where every card
  pulses on hover is slop.
- **Reduced motion is a first-class state, not an afterthought.** Every
  interaction defines its reduced-motion behaviour explicitly. Default:
  collapse spatial motion to opacity crossfade, keep duration ≤ 150ms,
  preserve functional state changes. <!-- rule:motion-reduced-motion-floor -->
- **Keyboard first, hover second.** Every hover affordance has a focus
  equivalent. No interaction is hover-only. <!-- rule:motion-keyboard-first -->

## The timing canon — mapped onto hub tokens

Pick from these buckets; do not invent new ones. Both source canons (the
80–500ms interaction buckets and the 100/300/500 rule) collapse onto the
hub §4 token set: <!-- rule:motion-timing-canon -->

| Hub token | ms | Upstream buckets | Use for |
|---|---|---|---|
| `--motion-instant` | 100 | 80–120ms · "100–150 instant feedback" | Button press tick, checkbox state, keystroke echo, toggle, colour shift. The brain reads this window as immediate. |
| `--motion-fast` | 150 | 150–200ms | Hover transitions, focus rings appearing, single-property fades, tooltip fade (after delay). |
| `--motion-normal` | 300 | 250–300ms · "200–300 state changes" | Modal / dropdown / sheet opens, content fades in, validation icon scales in, tab crossfade, menu open. |
| `--motion-slow` | 500 | 400–500ms · "300–500 layout changes" | Toast slide-in, page-load section reveal, accordion open, complex multi-property transitions. |
| `--motion-deliberate` | 800 | "500–800 entrance animations" | Hero reveal, one orchestrated page entrance — brand surfaces only, never product feedback. |
| *(no token)* | 0 | "0ms — the right answer surprisingly often" | Focus state, keyboard navigation, error appearance — many things should not animate at all. |

- **Exits run ~60–75% of the corresponding enter.** A 300ms enter pairs
  with a ~200ms exit — never the reverse.
  `calc(var(--motion-normal) * 0.75)` keeps it on-token.
  <!-- rule:motion-exit-75 -->
- **Feedback never exceeds 500ms** — beyond that it feels laggy.
  `--motion-deliberate` is for entrances, not feedback.
  <!-- rule:motion-feedback-500-ceiling -->
- Recipes below quote exact milliseconds; where a value matches a hub
  token (100/150/300/500/800) use the token var. In-between craft values
  (120, 180, 220, 250ms) stay literals or `calc()` on tokens — do not
  mint a parallel duration token set (the upstream `--dur-micro/short/long`
  sets are superseded by the hub tokens).

## The easing canon

Hub §4 defines the canonical tokens — `--ease-out:
cubic-bezier(0.25, 0, 0, 1)` and `--ease-spring:
cubic-bezier(0.16, 1, 0.3, 1)`. Note the name collision resolved in the
hub's favour: both upstreams call `cubic-bezier(0.16, 1, 0.3, 1)`
"ease-out" (ease-out-expo); in ArkaOS that exact curve is the hub's
`--ease-spring`. Use `--ease-out` for most transitions and hovers;
`--ease-spring` for entrances that visibly decelerate into place.
<!-- rule:motion-easing-tokens -->

Supplementary curves the recipes rely on (project-level tokens, allowed —
the hub does not define exit/toggle curves):

```css
:root {
  /* hub §4 — canonical */
  --ease-out:    cubic-bezier(0.25, 0, 0, 1);
  --ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
  /* supplementary — exits accelerate away, toggles are symmetrical */
  --ease-in:     cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}
```

Named deceleration flavours when `--ease-spring` is too aggressive:
ease-out-quart `cubic-bezier(0.25, 1, 0.5, 1)` (smooth) · ease-out-quint
`cubic-bezier(0.22, 1, 0.36, 1)` (snappier) · ease-out-expo
`cubic-bezier(0.16, 1, 0.3, 1)` (confident — = `--ease-spring`).

**Banned curves:** browser-default `ease` (flat and uncrafted); `linear`
except progress bars and infinite functional loaders; bounce
`cubic-bezier(0.34, 1.56, 0.64, 1)` and elastic
`cubic-bezier(0.68, -0.6, 0.32, 1.6)` — dated, they draw attention to the
animation itself, and bounce/elastic sits on the hub §4 forbidden list;
any overshoot above ~110%. <!-- rule:motion-banned-curves -->

**Spring physics** replaces eases for **physical** interactions only —
drag-and-drop release, swipe-to-dismiss, picker-wheel snap. Otherwise:
ease. Never spring the logo or brand marks (hub §4: bounce/elastic on the
logo is forbidden). <!-- rule:motion-springs-physical-only -->

| Spring config | Feel | Use for |
|---|---|---|
| `stiffness: 50, damping: 20` | Gentle, no overshoot | Calm reveals; almost an ease |
| `stiffness: 180, damping: 22` | Snappy, slight overshoot | Drag release; toggle handle |
| `stiffness: 280, damping: 26` | Stiff, minimal bounce | Picker snap; haptic-like press |
| `stiffness: 400, damping: 40` | Very stiff, no bounce | Position corrections |

For advanced sequences use libraries — GSAP first (hub §10: `gsap-core` +
`gsap-timeline`, `gsap-performance` as the review bar), Web Animations
API for programmatic control, Motion/Framer Motion on React.

## When to ship motion by default

The canon biases toward motion-cut, but certain page archetypes feel
**broken without** motion — so visually busy or number-led that complete
stillness reads as a screenshot. For these, ship 2–3 small purposeful
microinteractions automatically, without waiting for the user to ask.
<!-- rule:motion-default-on-archetypes -->

**Default-on archetypes:** Bento Grid · Stat-Led · Workbench · Marquee
Hero · Conversational FAQ.
**Default-off archetypes:** Editorial · Manifesto · Letter · Quote-Led ·
Type Specimen · Long Document · Index-First. There, motion is *opt-in* —
stillness is the brand.

For default-on, pick **two or three** from this menu (never more than
three primitives per page):

| Microinteraction | When to ship | Recipe |
|---|---|---|
| **Number reveal** | Stat-led hero, headline numbers | IntersectionObserver fires on viewport entry; `requestAnimationFrame` counts 0 → target over 1.2–1.6s with `--ease-out`. Reduced-motion: render final value. |
| **Pricing card lift** | Pricing tier cards | `translateY(-3px)` + shadow upgrade on `:hover`, 180ms `--ease-out`. Active: back to `translateY(0)` over 60ms (the press). |
| **CTA hover lift** | Primary CTA buttons | `translateY(-1.5px)` + background-fade, 200ms `--ease-out`. Active state at 60ms. |
| **Marquee scroll** | Marquee hero, logo strip | `@keyframes marquee` `translateX(-100%)` over 40–60s, infinite, pauses on hover. Reduced-motion: stop, show first three items. |
| **Stagger reveal** | Testimonials, feature cards, gallery | IntersectionObserver per card; 100ms stagger; opacity 0→1 + `translateY(8px → 0)`; `--ease-out` 400ms. **One-shot — never re-fires on scroll.** |
| **Recommended-tier pulse** | Middle pricing tier | One-shot `@keyframes pulse-border` 2s, runs once on viewport entry; border opacity 0.4 → 1 → 0.4. Don't loop. |
| **Caret blink** | *Inside* a typed command (install code, terminal nav) — never standalone decoration | `@keyframes blink` 1s steps(2) infinite on a 1ch block at the end of a typed line. Reduced-motion: solid block. **Hard rule:** the caret sits inside `<pre class="code">…▮</pre>` — never a floating `<span>` in a hero. |
| **Number tick on data update** | Dashboard live values | See *Number tick* recipe below. |

### Hard rules for default-on motion

1. Every animation respects `prefers-reduced-motion: reduce` — skip
   entirely or run ≤ 150ms opacity-only.
2. **No more than three distinct animation primitives per page.** A
   counter + a hover-lift + a marquee = three. The temptation to layer
   "just one more" is the slop pull. <!-- rule:motion-three-primitives-cap -->
3. No scroll-linked animations on viewports below 40rem.
4. No animation longer than 2s except continuous functional loops
   (marquee, caret blink, loaders). Infinite loops anywhere else pull the
   eye and never let go.
5. The "if I removed this animation, would anyone notice?" test still
   applies — for the default-on set the answer is "yes, the page would
   feel screenshot-stiff."

### What never gets default motion

- Body text reveals on scroll. Reading is not a cinematic experience.
- Background gradient shifts. Distracting.
- Cursor followers. Always slop.
- Section-by-section fade-up-stagger. Pick one orchestrated entrance,
  not twelve (law: hub §12).
- Tab content sliding sideways. Crossfade only (see Tab change below).
- Confetti, particle bursts, "success celebrations" — particles are hub
  §4 forbidden, and silent success is the taste marker anyway.
- Icon spin/rotation flourishes (like-button rotation, loading logos) —
  rotation/spin is hub §4 forbidden; indicate state by swap, translate,
  or opacity instead.

## Recipes

Each recipe: trigger, what changes, duration, easing, accessibility note.
If a recipe is missing here, return to the principles and derive it.

### 1 · Button press

Trigger: pointer down. Changes: `transform: scale(0.98)` on press, base
styling on release. Duration: 100ms in (`--motion-instant`), 150ms out
(`--motion-fast`). Easing: in `--ease-in`, out `--ease-out`. A11y: focus
ring stays visible; never animate the focus ring's existence.

```css
.btn {
  transition: background-color var(--motion-fast) var(--ease-out),
              transform var(--motion-instant) var(--ease-out);
}
.btn:hover { background: var(--color-ink); color: var(--color-paper); }
.btn:active { transform: translateY(1px); }
.btn:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 3px; }
```

Hover scale (1.02–1.05) is legal only as the *one* chosen hover signal on
a specific element — universal `hover:scale-105` is tell #2 below.

### 2 · Input focus + label float

Trigger: focus event. Changes: border-bottom colour, label slides up +
shrinks, optional subtle background tint. Duration: 200ms. Easing:
`--ease-out`. **Critical:** the change happens *before* the user types —
Stripe / Linear use this to confirm the field is alive. A11y:
`:focus-visible` only; reduced-motion removes the slide, keeps the colour
change.

### 3 · Form validation

Trigger: blur after the field has been touched once (the "touched"
pattern), then re-validate on every input. Never validate on every
keystroke from the start — it's hostile. Changes: icon scales in (200ms
`--ease-out`), border tints, helper text replaces. Three-part error
message: what broke, why, how to fix.

### 4 · Toast notification

Trigger: action completes (or fails). Stack at one viewport corner; new
toasts push in one direction; existing toasts do **not** reposition when
a new one arrives. Duration: 400ms slide-in `--ease-out`, 4–6s dwell,
300ms slide-out `--ease-in`. Pause auto-dismiss on hover/focus. **Use
sparingly:** if the action's effect is visible, no toast. Errors *always*
get a toast with retry/undo.

### 5 · Modal open / close

Trigger: explicit user action. Backdrop fades 300ms (`--motion-normal`)
`--ease-out`. Content scales 0.96 → 1.0 + opacity 0 → 1, 300ms
`--ease-out`. Close: 220ms `--ease-in`, scale to 0.98, opacity → 0. Use
native `<dialog>` — focus trap and `::backdrop` for free; `inert` on the
background. First focus to the first interactive element, not the close
button. Reduced motion: opacity-only crossfade, 150ms.

### 6 · Dropdown / menu

Trigger: click or key shortcut. Open: 180ms `--ease-out`, optional
30ms-stagger items when ≤ 8. Close: 140ms `--ease-in`. Light-dismiss on
outside click and Escape. Use the Popover API where available. Anchor
positioning: flip when within 16px of the viewport edge.

### 7 · Tooltip

Trigger: mouse hover (with **800–1000ms delay** to prevent flash on
casual movement) OR keyboard focus (with **0ms delay** — keyboard users
reached this deliberately, never delay them). Animation: 150ms
(`--motion-fast`) `--ease-out` opacity. WCAG 1.4.13: hoverable,
persistent, dismissible (Escape).

### 8 · Tab change

Trigger: click or arrow-key. Underline slides `transform: translateX()` +
width transition, 250ms `--ease-out`. Outgoing content fades 100ms
`--ease-in`, incoming fades 150ms `--ease-out` with a 50ms delay. **Never
animate the tab content's height** — animate
`grid-template-rows: 0fr → 1fr` if the tabs change height.

### 9 · Number tick

Trigger: data loaded. Counter increments 0 → value over 400ms with
`--ease-out` applied to the *value*, not the element. Use
`Intl.NumberFormat` for locale-correct separators. A11y: announce the
final value with `aria-live="polite"`, *not* every tick. Reduced motion:
skip the tick, show the final value.

### 10 · Copy-to-clipboard

Trigger: click. Changes: button label swaps to "Copied" with a check
icon; revert after 2.5s. **No toast.** The label change *is* the
feedback. Restore on `mouseleave` if the user moves away sooner.

```js
btn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(value);
  btn.dataset.state = "copied";
  setTimeout(() => delete btn.dataset.state, 2500);
});
```

### 11 · Drag handle

Trigger: hover (after **1–2s delay** — Notion's pattern). Changes: handle
reveals via opacity, cursor switches to `grab`. On grab: cursor
`grabbing`, ghost element at 50% opacity follows the pointer, drop
indicator (1px line, accent colour) tracks the nearest valid target.
Spring stiffness 280 / damping 26 on release-snap (physical interaction —
springs allowed). A11y: arrow-key reorder when the row is focused;
announce drag state with `aria-live`.

### 12 · Optimistic update with rollback

Trigger: any action with a known-correct local prediction (toggle, like,
archive, reorder). State mutates immediately; async request fires. On
success: nothing happens — silent success is the marker of taste. On
failure: 200ms colour rollback + a toast with one Undo button that does
not auto-dismiss while the user might still want it. Low-stakes actions
only — never payments or destructive operations.

```js
const prevState = item.completed;
item.completed = !prevState; render();
try {
  await api.update(item);
} catch {
  item.completed = prevState; render();
  toast({ tone: "error", message: "Couldn't save.", action: { label: "Try again", run: retry } });
}
```

### 13 · Search-as-you-type

Trigger: input event. Debounce 250ms before requesting; while debouncing,
show a subtle indicator (border opacity or label colour shift). Highlight
matches with `<mark>`. A11y: announce result count with
`aria-live="polite"` after the debounce settles, never per keystroke.

### 14 · Command palette navigation

Trigger: ⌘K or `/`. Open: instant, no animation. Arrow-keys move
selection — **the indicator transitions** between rows (120ms `--ease-out`
on the highlight's `translateY()`), the items themselves don't move.
Enter selects, Escape closes. Items stagger-fade on first open only,
never on filter change. The text input stays focused throughout. This is
the Linear / Raycast / Vercel pattern.

### 15 · Page-load reveals

One orchestrated entrance. Stagger by DOM index via a CSS custom
property, capped at ~500ms total (10 items × 50ms, or fewer items ×
60ms). Use IntersectionObserver, never scroll listeners. After the first
reveal, no more on-scroll animations — let the page just *be there*.
Print-metaphor and soft-gallery directions skip reveals entirely; that is
correct, not a bug. Reveals must enhance an already-visible default —
never gate content visibility on a class-triggered transition (ships
blank in hidden tabs and headless renderers; law: hub §12).
<!-- rule:motion-stagger-cap -->

```html
<section style="--i: 0">…</section>
<section style="--i: 1">…</section>
```

```css
.reveal {
  opacity: 0;
  transform: translateY(8px);
  animation: reveal var(--motion-slow) var(--ease-spring) forwards;
  animation-delay: calc(var(--i, 0) * 60ms);
}
@keyframes reveal { to { opacity: 1; transform: none; } }
```

## Motion materials — what to animate

**Transform and opacity are the reliable defaults** — GPU-composited, no
layout work — but not the whole palette. Premium interfaces often need
atmospheric properties; match material to effect:
<!-- rule:motion-transform-opacity-default -->

- **Transform / opacity** — movement, press feedback, simple reveals,
  list choreography.
- **Blur / filter / backdrop-filter** — focus pulls, depth, glass or lens
  effects, softened entrances.
- **Clip-path / masks** — wipes, reveals, editorial cropping,
  product-like transitions.
- **Shadow / glow / colour filters** — energy, affordance, focus, active
  state. (Never a `box-shadow` hover transition on a dark background —
  reads as glow.)
- **`grid-template-rows` or FLIP-style transforms** — expanding and
  reflowing layout without animating `height` directly (accordion:
  `0fr → 1fr` with `--ease-in-out`).

The hard rule isn't "transform and opacity only" — it's: never animate
layout-driving properties casually (`width`, `height`, `top`, `left`,
margins, padding trigger reflow every frame); keep expensive effects
bounded to small or isolated areas (`contain` where appropriate); verify
smoothness in-browser at 60fps on target viewports.
<!-- rule:motion-materials-palette -->

- `will-change` sparingly, for known-expensive animations only (on
  `:hover` or an `.animating` class) — never preemptively across a whole
  class of elements.
- Scroll-linked motion: IntersectionObserver, **never** `scroll` event
  listeners; unobserve after the reveal fires once; reveal-once effects
  only — no parallax, no scroll-scrubbing without a specific reason.
  (This skill's video-scroll canvas engine *is* that named reason — the
  scrub is the product; everything else on the page still follows these
  rules, and the reduced-motion fallback stays mandatory.)
  <!-- rule:motion-intersection-observer -->

## Perceived performance

Nobody cares how fast the site *is*, only how fast it feels.

- **The 80ms threshold:** anything under ~80ms feels instant — the brain
  buffers sensory input that long to synchronise perception. Target it
  for micro-feedback. <!-- rule:motion-80ms-instant -->
- **Preemptive start:** begin transitions immediately while loading
  (skeleton UI, app-zoom). Users perceive work happening.
- **Early completion:** show content progressively — progressive images,
  streaming HTML, skeleton fade-ins — don't wait for everything.
- **Spinner discipline:** either delay showing a spinner (150ms) or give
  it a minimum visible duration (300ms); a spinner that flashes for 80ms
  reads as a glitch.
- **Easing shapes perceived duration:** ease-in (accelerating toward
  completion) makes tasks feel shorter (peak-end effect); ease-out feels
  satisfying for entrances.
- **Caution:** too-fast responses can decrease perceived value for
  complex operations (search, analysis) — a brief delay can signal real
  work.

## The named tells (what AI defaults produce)

The microinteraction signatures of generated code. The slop test
(`departments/brand/skills/design-review/references/slop-test.md`) checks
for them; treat any one as a critical finding. <!-- rule:motion-tells -->

1. **`transition-all`.** Every property animating, including ones that
   should be instant (visibility, display, focus rings). Always specify
   the properties. Banned outright.
2. **Universal `hover:scale-105`.** Every card lifts on hover with no
   shadow change, no easing, no purpose — the reflexive "make it
   interactive" gesture.
3. **Bouncy overshoot easings.** `cubic-bezier(0.34, 1.56, 0.64, 1)` and
   friends on UI elements. Reserve overshoot for genuine physical
   interactions (drag release); banned on everything else (hub §4).
4. **Multiple simultaneous hover effects.** A card that translates,
   scales, shadows, colour-shifts, and rotates on hover. Pick *one*
   signal.
5. **Animated gradient backgrounds on hover.** Distracting, expensive,
   communicates nothing.
6. **Glow halos on text.** Heavy `text-shadow` for "neon" — destroys
   contrast and legibility.
7. **Cursor-follower dots.** Adds nothing; triggers vestibular issues.
8. **Custom cursors on every interactive element.** Conflicts with OS
   conventions; users learn nothing about what's clickable.
9. **Auto-rotating carousels with no controls.** WCAG 2.2.2 violation.
   Always.
10. **Parallax on scroll.** Layers moving at different speeds —
    vestibular trigger; rarely serves the content.
11. **`transition` on layout properties.** Animating `width`, `height`,
    `padding`, `margin`, `top`, `left` triggers reflow every frame. Use
    `transform` or `grid-template-rows: 0fr → 1fr`.
12. **Universal scroll-triggered fade-up-stagger.** Every section fades
    in on intersection; the page never settles. Both upstreams name this
    one — the saturated AI default (law: hub §12). Pick *one*
    orchestrated entrance.
13. **Celebratory success toasts.** "Done!" when the user can see the
    thing was saved. Silent success is taste.
14. **Confirmation dialogs for reversible actions.** Replace with
    optimistic action + Undo toast.
15. **Spinners with no minimum visible time.** See spinner discipline
    above.
16. **Tooltips with the same delay on hover and focus.** Hover delays
    800–1000ms; focus appears immediately. Different intents.
17. **Focus rings that animate in.** Keyboard users lose the indicator
    during the transition. Focus rings appear instantly. Always.
    <!-- rule:motion-focus-ring-instant -->
18. **Colour-only state change.** A field turns red with no icon, no
    text, no border change. Fails WCAG 1.4.1.
19. **Toasts that move existing content.** Stack toasts; never shift
    layout.
20. **Hover delays on touch.** A `:hover` state the touch user can never
    reach because there's no focus/tap equivalent.

## Direction-aware duration multipliers

The same button press is louder in a brutalist direction than in a soft
gallery. Apply a multiplier per aesthetic direction:
<!-- rule:motion-theme-multipliers -->

| Aesthetic direction | Duration scale | Easing flavour | Notes |
|---|---|---|---|
| Restrained default | 1.0× | `--ease-out` | The baseline. |
| Dark / technical | 0.9× | `--ease-out` | Snappy, precise. |
| Brutalist | 0.75× | `--ease-out` (sharper) | Fast, decisive. No spring. |
| Organic / garden-calm | 1.2× | `--ease-out` | Calm. Springs welcome (physical only). |
| Atelier-soft / gallery | 1.3× | `--ease-out` (very gentle) | Generous; almost no movement. |
| Newsprint / print metaphor | 0× | none | Static. Print metaphor. |
| Terminal / mono | 0× | none, except caret blink *inside* a typed command | No standalone blinking cursor — the caret only blinks where the user would type. |
| Manifesto / declarative | 0.7× | `--ease-out` (sharp) | Snap into place. |
| Almanac / reference | 0.85× | `--ease-out` | Functional, like a reference book. |
| Sport / energetic | 0.7× | `--ease-out` (sharp) | Quick, italic-energy. |

If the direction has duration scale `0×`, you do not animate. The page
does not move. That is a deliberate design choice, not a bug.

## Accessibility ground truth

Every recipe must pass these checks before shipping.

- **`prefers-reduced-motion: reduce` is honoured — mandatory, no
  exceptions.** Spatial motion collapses to opacity crossfade ≤ 150ms;
  functional state changes (progress bars, spinners, skeletons) slow but
  remain:

  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 150ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 150ms !important;
    }
    .reveal { animation: reveal-reduced 150ms linear forwards; }
    @keyframes reveal-reduced { to { opacity: 1; transform: none; } }
  }
  ```

- **Focus rings** 2–3px, ≥ 3:1 contrast, never animated in/out, present
  on every interactive element via `:focus-visible`.
- **Hit targets** ≥ 44 × 44 CSS px on touch surfaces.
- **No reliance on colour alone** for state — pair with icon, text, or
  pattern.
- **No flashing** above 3 Hz; even subtle pulses need rate caps.
- **Keyboard equivalents** for every hover affordance. No exceptions.
- **`aria-live`** on async state updates — `polite`, not `assertive`,
  unless safety-critical.
- **Don't block interaction** during or after animations unless the
  block is the point (destructive confirm).

## When in doubt, cut

Most pages have too much motion, not too little. Before shipping, walk
through every animation and ask: *what would happen if this were
instant?* If the answer is "nothing — the user wouldn't notice", remove
it. If the answer is "the user would lose information about what
changed", keep it. Reaching for a static answer is a sign of taste;
reaching for more motion is the AI default. <!-- rule:motion-when-in-doubt-cut -->
