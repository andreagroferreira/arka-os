# UI/UX Knowledge & Tools — Squad Reference

> Shared reference for the frontend UI/UX squad: **Diana** (frontend-dev),
> **Sofia D.** (ux-designer), **Isabel** (visual-designer), **Rafael**
> (motion-designer) and **Valentina** (creative-director).
>
> Read this BEFORE any UI/UX work. It defines the non-negotiable KB-first
> rule, the canonical knowledge sources, the concrete design tokens, the
> motion system, the new tooling, the squad validation order, the canonical
> reflex-reject lists (§11) and the hard design laws (§12).

---

## 1. KB-First (NON-NEGOTIABLE)

**The Obsidian knowledge base is the canonical, primary source for every
agent and every team.** New tools (Magic, Motion, ui-ux-pro-max, context7,
nuxt-ui) are **supplements** — they never replace the vault.

Order of operations on ANY UI/UX task:

1. **Search the Obsidian KB first** (`mcp__obsidian__search_notes` /
   `read_note`). Start from the canonical sources in §2.
2. **Cite what you found** with `[[wikilinks]]`, or explicitly declare a
   KB gap if nothing relevant exists.
3. **Only then** supplement with the tools in §5 for theory the vault
   lacks (see §7).
4. When external research produces something material, **write it back to
   the KB** so the vault gets richer over time.

This mirrors the Synapse L2.5 pre-injection and the `kb-first` constitution
rule. Operator directive (2026-05-30): *"a prioridade é sempre a base de
conhecimento que temos no Obsidian — para qualquer agent ou equipa."*

---

## 2. Canonical KB Sources

| Source (Obsidian) | What it gives you |
|---|---|
| `[[ArkaOS-Brand-Guidelines-v2]]` | **Primary.** Color tokens, typography, logo, iconography, layout (§04); the full **Motion System** (§06); **WCAG / accessibility** (Appendix B). Concrete, ready-to-code values. |
| `[[Area 02 - Design]]` | Framework index: Nielsen, Laws of UX (Yablonski), Krug, Garrett's 5 Planes, Cooper, Norman, Double Diamond, Design Sprint. Names the bodies of theory (see §7 for depth gaps). |
| `[[ArkaOS-Persona-Squad-Matrix]]` | Persona × framework × squad mapping (NN/g for Francisca; Two-Part Conversion Formula; archetypes for Valentina). |
| `[[Universal Component Language]]` | Alani Nicolas: 39 design systems → shadcn interlingua; token-extraction pipeline (OKLCH normalization → WCAG audit → Atomic Design). |
| `[[Design-Tokens-v1]]` (Hringr) | DTCG token architecture: primitive → semantic → component. Reference model for token discipline. |
| `[[19-Video-Motion-Designer]]` ("Kubrick") | Cinematic motion/video persona — base voice for Rafael's video work. |

---

## 3. Design Tokens — Quick Reference

From `[[ArkaOS-Brand-Guidelines-v2]]` §04 (verify against the note before use):

- **Composition ratio 60 / 25 / 15** — canvas / content / signal (accent
  green 10–15% max).
- **Spacing** base 4px scale: `space-1`=4px … `space-24`=96px.
- **Type**: never body < 16px; line-height 1.5–1.6× body, 1.1–1.2× display;
  max line length ~75 chars; max 2 families + mono for code.
- **Surface hierarchy**: 5 layers (0→4), 1px edge border mandatory.
- **Radius** scale 4px → full; **grid** 12-column, max content 1280px.
- **Icons**: stroke 1.5px, 24×24 grid, optical alignment.

> Always read the live note for the exact HEX/token names — do not
> hardcode values from memory.

---

## 4. Motion System

From `[[ArkaOS-Brand-Guidelines-v2]]` §06. **5 principles** (inject verbatim):

1. **Purposeful** — every animation answers "what does it communicate?"; if nothing, remove it.
2. **Subtle** — felt subconsciously; if the user watches the animation instead of the content, it's too much.
3. **Precise** — intentional easing, exact timing.
4. **Fast** — CLI-first product; default to the fastest option.
5. **Consistent** — same action → same animation everywhere.

**Timing tokens**: `motion-instant` 100ms · `motion-fast` 150ms (default) ·
`motion-normal` 300ms · `motion-slow` 500ms · `motion-deliberate` 800ms.
**Easing**: `--ease-out` cubic-bezier(0.25,0,0,1); `--ease-spring`
cubic-bezier(0.16,1,0.3,1).

**Forbidden**: rotation/spin, bounce/elastic on the logo, 3D/perspective,
particles, morphing, color-cycling.

**Accessibility**: always honour `prefers-reduced-motion`.

---

## 5. Tools (supplement only — after KB)

| Tool | Type | Use for | Notes |
|---|---|---|---|
| **Magic** (`@21st-dev/magic`) | MCP (user scope) | Generate production UI components from natural language, framework-aware (Nuxt UI, Tailwind, shadcn) | Preferred path for frontend UI/UX — mandatory when configured. Wired into nuxt/vue/react/nextjs/full-stack MCP profiles. Needs `MAGIC_API_KEY` (falls back gracefully when absent). |
| **Motion** (`motion-ai` kit) | MCP + skills | Animation/motion implementation (Motion library) | Auto-installed on install/update. Pair with the §4 motion system. |
| **ui-ux-pro-max** | Claude plugin | UI/UX methodology + patterns, conjugated with whatever framework is in use | Marketplace `nextlevelbuilder/ui-ux-pro-max-skill`. Use to fill the §7 theory gaps. |
| **nuxt-ui** / **context7** | MCP | Up-to-date framework + component docs | Use for current API/usage instead of memory. |
| **playwright** | MCP | Verify the UI in a real browser before claiming done | Constitution: test before claim. |

Framework-agnostic rule: detect the project's framework first (Nuxt UI,
Tailwind, shadcn, …) and conjugate Magic + ui-ux-pro-max to THAT framework.

---

## 6. Squad Validation Order (NON-NEGOTIABLE)

**Diana (frontend-dev) implements UI ONLY after the UI/UX design agents
have analysed and their output is validated.** No interface freelancing.

```
1. Sofia D. (ux-designer)      → UX analysis: flows, IA, heuristics, accessibility
2. Isabel (visual-designer)    → visual direction: tokens, hierarchy, components
3. Rafael (motion-designer)    → motion/interaction direction (where relevant)
4. Valentina (creative-director) → validates direction against brand strategy
   ───────────────────────────────────────────────────────────────────────
5. Diana (frontend-dev)        → implements the VALIDATED design with Magic +
                                  the project framework, then QA + Quality Gate
```

Operator directive (2026-05-30): *"o frontend developer só faz alguma coisa
com validação e sempre depois da análise dos outros agentes de UI/UX."*

---

## 7. Theory Gaps (KB-thin → supplement, then write back)

The KB is rich in **applied** knowledge (tokens, motion, WCAG application)
but thin on **theory**. For these, consult ui-ux-pro-max + context7, then
write material findings back to `[[Area 02 - Design]]`:

- Nielsen's 10 heuristics in detail
- Laws of UX (each law)
- Dieter Rams' 10 principles
- Atomic Design (full atoms→pages)
- Microinteractions (trigger→rules→feedback→loops/modes)
- Color theory & typography science (OKLCH, harmony, modular scale) —
  **partially filled in-repo**: hard floors/ceilings now live in §12 and
  the reflex-reject discipline in §11; deeper craft references live under
  `departments/brand/skills/design-review/references/`.
- Gestalt & visual hierarchy (F/Z scanning, proximity, contrast)

---

## 8. Anti-Default Doctrine (NON-NEGOTIABLE — excellence-mandate)

AI-generated design clusters around three default looks. Producing any of
them WITHOUT a brief that explicitly asks for it is a constitution
violation (`excellence-mandate`: "no default-looking output"):

1. **Cream + serif + terracotta** — warm cream background (≈ `#F4F1EA`),
   high-contrast serif display, terracotta accent.
2. **Dark + acid accent** — near-black background with a single bright
   acid-green or vermilion accent.
3. **Broadsheet** — hairline rules, zero border-radius, dense
   newspaper-like columns.

These are defaults, not choices. Where the brief pins a direction, the
brief wins — including when it asks for one of these. Where an axis is
free, never spend it on a default.

**Token-plan-then-critique loop** (before writing any code or asset):

- **Color**: palette as 4–6 NAMED hex values (name = role, not "blue").
- **Type**: faces for 2+ roles — characterful display used with restraint,
  complementary body, utility for captions/data when needed.
- **Layout**: one-sentence concept + ASCII wireframe to compare options.
- **Signature**: the ONE element this design will be remembered by.
  Spend your boldness there; keep everything else quiet and disciplined.

Then critique the plan BEFORE building: *"would this exact design appear
for any other brief?"* If yes, revise and state what changed and why.
Quality floor, never announced: responsive to mobile, visible keyboard
focus, `prefers-reduced-motion` respected, WCAG AA contrast.

**Pre-emit critique (scored — hallmark protocol).** Before handing back
any design artifact, score it 1–5 on six axes:

| Axis | Question |
|---|---|
| **P** Philosophy | Does the design have a stated POV the brief earns? |
| **H** Hierarchy | Does the eye land where the content says it should? |
| **E** Execution | Are spacing, contrast, states, and breakpoints finished? |
| **S** Specificity | Does this look like *this brief* — or a generic page? |
| **R** Restraint | Is every bold move deliberate; is everything else quiet? |
| **V** Variety | Does it differ structurally from the previous output? |

Any axis **< 3 triggers a revision pass** — never ship and explain.
Stamp the six scores in the artifact via the `[arka:design-dna]` companion
stamp (§9). The 58 pass/fail slop gates that operationalize this rubric
live in `departments/brand/skills/design-review/references/slop-test.md`.

## 9. Design Marker Contract (`[arka:design]`)

Every UI/design-producing turn MUST emit the structured marker on its own
line BEFORE the first file edit:

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

- `benchmark=` — named reference company (Linear, Stripe, Vercel, Notion,
  Airbnb…). Pick it FIRST and state what its design lead would reject in
  your plan.
- `skills=` — the design skills ACTUALLY loaded this session via the
  Skill tool (e.g. `frontend-design,ui-ux-pro-max,gsap-core`). If a
  plugin is not installed, be honest: `skills=degraded:<missing-name>`
  and fall back to §3 + §8 of this reference. Never claim a load that
  did not happen; never silently proceed as if it had.
- `tokens=` — path of the project design-system source
  (`design-system.yaml`, tokens file), or `none` + one-line justification.

A bare `[arka:design] <token>` is a LEGACY marker: tolerated in WARN mode,
counted separately in telemetry, and treated as missing once the frontend
gate goes hard.

**Companion stamp `[arka:design-dna]` (informational).** Design-producing
work additionally stamps the first non-empty line of produced CSS with:

```
/* [arka:design-dna] macrostructure=<name> genre=<genre> anchor=<oklch|hex> display=<font> body=<font> critique=P#H#E#S#R#V# */
```

Key=value, single line, greppable. It records the structural choice, the
palette anchor, the type pairing, and the six pre-emit critique scores
(§8), and feeds the structural-diversification rule (consecutive outputs
must differ on at least one axis; project memory at
`.arka/design/log.json`). This stamp is **NOT parsed by the frontend gate**
(`core/workflow/frontend_gate.py`) and carries no gate semantics — the
structured `[arka:design]` marker above remains the only enforced line.

## 10. Aesthetic Directions Catalog (optional, curated)

When a project has NO design system yet and the brief leaves the visual
axis free, seed a direction from the curated TypeUI catalog
(`npx typeui.sh pull <slug>` — MIT, bergside/awesome-design-skills):

`editorial` · `brutalism` · `neobrutalism` · `bento` · `expressive` ·
`dramatic` — anti-default directions; `shadcn` · `mono` — clean baselines.

Catalog tokens are a SEED for the project's own token system, never the
final design system. Motion is absent from the catalog — that is GSAP's
job: load `gsap-core` + `gsap-timeline` for any animation work,
`gsap-scrolltrigger`/`gsap-plugins` as the work demands, `gsap-react` on
React, and treat `gsap-performance` as the review bar
(`npx skills add https://github.com/greensock/gsap-skills` when absent).

## 11. Canonical Reflex-Reject (fonts + aesthetic lanes)

> Derived from [impeccable](https://github.com/pbakaus/impeccable)
> (Apache-2.0) and [hallmark](https://github.com/nutlope/hallmark) (MIT) —
> license texts at `departments/brand/skills/design-review/references/`.
> This section is the SINGLE canonical home of the list. Skills and gates
> point here; they never restate it (drift risk).

These are **training-data defaults**: every LLM reaches for them by
reflex, which is exactly why using them by reflex produces monoculture.
The semantics are **never-by-reflex**, not never:

1. **Identity-preservation carve-out** — when the existing brand has
   already committed to a font or lane, identity wins. The list governs
   greenfield decisions only.
2. **Deliberate-pick carve-out** — a listed font may be used when a named
   theme or brief *deliberately* selects it and the choice is stated with
   its reason (e.g. Playfair Display as display-only in an editorial
   theme; Space Grotesk in a brutalist direction). Reflex is the crime,
   not the font.
3. **Product-register carve-out** — product UI (design SERVES the task)
   has explicit permission for system fonts and familiar sans defaults
   (Inter, SF Pro, system-ui). The ban list bites on BRAND surfaces
   (design IS the product). See
   `departments/brand/skills/design-review/references/design-registers.md`.

### Reflex-reject fonts

**Sans:** Inter · DM Sans · Space Grotesk · Outfit · Plus Jakarta Sans ·
Instrument Sans · Syne · Roboto · Open Sans · Lato · Poppins · Source Sans ·
Nunito · Montserrat · Raleway · Work Sans · system-ui-as-brand · Arial ·
Helvetica-as-default
**Serif:** Fraunces · Newsreader · Lora · Crimson / Crimson Pro / Crimson
Text · Playfair Display · Cormorant / Cormorant Garamond · DM Serif Display ·
DM Serif Text · Instrument Serif · Merriweather · Source Serif ·
Georgia-as-default
**Mono:** IBM Plex Mono · Space Mono · Courier New · Consolas-as-default ·
system-mono-as-brand
**Family-wide:** IBM Plex Sans · IBM Plex Serif

Selection discipline when rejecting a reflex pick: run the 4-step
physical-object font procedure in `design-registers.md` (three concrete
brand-voice words → reject reflex picks → browse a real catalog for the
brand as a physical object → cross-check).

### Reflex-reject aesthetic lanes

- **Editorial-typographic** — display serif (often italic) + small mono
  labels + ruled separators + monochromatic restraint. The 2026 fingerprint:
  three rule-separated columns, an italic serif headline, lowercase
  track-spaced metadata, no imagery. Every Stripe-adjacent and
  Notion-adjacent brand has landed here. Requires a register reason that
  *demands* it (a literal magazine), not a mood.

Lanes saturate and desaturate over time — entries move in and out on
evidence, mirroring upstream. The **second-order slop check** applies: if
the aesthetic family is guessable from category-plus-anti-references
("fintech that's not navy-and-gold → terminal-native dark mode"), it is
the trap one tier deeper. Rework until neither the first-order nor the
second-order answer is obvious.

## 12. Design Laws (hard floors and ceilings)

> Derived from [impeccable](https://github.com/pbakaus/impeccable)
> (Apache-2.0) and [hallmark](https://github.com/nutlope/hallmark) (MIT).
> Compact canonical table — one law per line. The enforcement surfaces
> (slop gates, design-slop detector, QG visual review) cite these; deeper
> rationale lives in `design-review/references/`.

**Typography**
- Body contrast ≥ 4.5:1; large text (≥18px, or bold ≥14px) ≥ 3:1;
  placeholders need 4.5:1 too — muted-gray-on-tinted-near-white is the
  single biggest readability failure.
- Prose line length 65–75ch (dense data UI may run denser).
- Hero/display ceiling: `clamp()` max ≤ 6rem. Above that the page shouts.
- Display letter-spacing floor ≥ −0.04em — tighter and letters touch.
- `text-wrap: balance` on h1–h3; `text-wrap: pretty` on long prose.
- Max 3 font families per page (display + body + one outlier). Four = slop.
- Pair on a contrast axis (serif+sans, geometric+humanist) or use one
  family with committed weight contrast — never two similar sans.
- Light-on-dark compensation runs on three axes: line-height +0.05–0.1,
  letter-spacing +0.01–0.02em, optionally body weight one notch up.
- Commit to extremes: weight 200 next to 800 reads as intentional;
  400 next to 600 reads as a default setting.

**Color**
- OKLCH for new palettes. Pure gray is dead: tint neutrals 0.005–0.015
  chroma toward the brand hue (never default-tint warm/cool).
- The warm-neutral band (L 0.84–0.97, C < 0.06, hue 40–100) is the
  saturated AI default — cream/sand/paper by any token name
  (`--paper`, `--cream`, `--sand`, `--linen`, `--parchment`…) is a tell.
  Warmth is carried by accent + typography + imagery, not body bg.
- Pick a color strategy BEFORE colors, on the commitment axis:
  **Restrained** (neutrals + one accent ≤10%) · **Committed** (one
  saturated color, 30–60% of surface) · **Full palette** (3–4 named
  roles) · **Drenched** (the surface IS the color).
- Gray text on colored backgrounds washes out: use a darker shade of the
  background's own hue or a transparency of the text color.
- Button text vs fill must differ by > 5% lightness or > 0.05 chroma in
  OKLCH (catches the black-on-black bug).
- Heavy alpha/transparency is a design smell — it usually means an
  incomplete palette.

**Layout**
- Nested cards are always wrong; cards only when truly the best affordance.
- Flexbox for 1D, Grid for 2D; breakpoint-free grids via
  `repeat(auto-fit, minmax(280px, 1fr))`.
- Semantic z-index scale (dropdown → sticky → modal-backdrop → modal →
  toast → tooltip); never 999/9999.
- Vary spacing for rhythm: generous separations, tight groupings —
  monotonous spacing is a tell.
- Touch targets ≥ 44×44 (extend hit area via `::before { inset: -10px }`
  when the visual must stay smaller).

**Motion**
- Ease out with exponential curves (ease-out-quart/quint/expo); no bounce,
  no elastic, no browser-default `ease`.
- Exits run ~75% of the enter duration.
- `prefers-reduced-motion` alternative is mandatory for every animation.
- Never animate CSS layout properties without real need; motion conveys
  state on product surfaces, never decoration.
- The uniform fade-and-rise reveal on every scrolled section is a tell —
  each reveal fits what it reveals; zero motion is not the fix either.
- Reveal animations enhance an already-visible default — never gate
  content visibility on a class-triggered transition (ships blank in
  hidden tabs and headless renderers).

**Interaction**
- Every interactive element ships all 8 states: default, hover,
  focus-visible, active, disabled, loading, error, success. Missing any =
  unfinished.
- Skeletons for loading, not spinners in content; empty states teach the
  interface.
- Modal as first thought is laziness — exhaust inline/progressive
  alternatives first.

**Absolute bans (match-and-refuse — rewrite the element, never ship):**
side-stripe borders (`border-left/right` > 1px as accent) · gradient text
(`background-clip: text`) · glassmorphism-as-default · the hero-metric
template (big number + small label + gradient accent) · identical
icon+heading+text card grids · tiny uppercase tracked eyebrow above every
section · numbered section markers (01/02/03) as default scaffolding ·
text overflowing its container at any breakpoint.

These laws are floors, not aspirations: §8's three default looks plus any
absolute-ban hit are constitution violations under `excellence-mandate`.
