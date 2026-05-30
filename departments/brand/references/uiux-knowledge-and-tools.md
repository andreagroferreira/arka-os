# UI/UX Knowledge & Tools — Squad Reference

> Shared reference for the frontend UI/UX squad: **Diana** (frontend-dev),
> **Sofia D.** (ux-designer), **Isabel** (visual-designer), **Rafael**
> (motion-designer) and **Valentina** (creative-director).
>
> Read this BEFORE any UI/UX work. It defines the non-negotiable KB-first
> rule, the canonical knowledge sources, the concrete design tokens, the
> motion system, the new tooling, and the squad validation order.

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
- Color theory & typography science (OKLCH, harmony, modular scale)
- Gestalt & visual hierarchy (F/Z scanning, proximity, contrast)
