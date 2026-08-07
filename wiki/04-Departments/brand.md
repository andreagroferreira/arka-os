# Brand & Design

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/brand` · **Lead:** Valentina (Tier 1) · **Agents:** 10 · **Skills:** 16

Brand & Design is the squad that turns strategy into identity. It covers the full spectrum from brand positioning and naming through visual system production, UX research, component library standardization, and accessibility conformance. The guiding principle is that visual decisions must trace back to strategic ones: the squad never opens a design tool before completing the strategy, verbal identity, and architecture phases.

Reach for this squad when you are starting a new brand, overhauling an existing one, building or extending a design system, running a UX audit, or need any artefact — logo, color palette, voice guide, wireframe, mockup — that will represent the product to the world.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 12 | 16 | 10 |

**Commands** (12 via `/brand`):

| Command | What it does |
| --- | --- |
| `/brand audit` | Brand audit against Primal Code completeness |
| `/brand colors <mood>` | Color palette design with theory |
| `/brand design-system` | Design system specification (Atomic Design) |
| `/brand guidelines` | Compile brand guidelines document |
| `/brand identity <name>` | Full brand identity (strategy to visual system) |
| `/brand logo <brief>` | Logo concept generation with AI |
| `/brand mockup <type>` | Generate mockups with AI image generation |
| `/brand naming <project>` | Brand naming with SMILE/SCRATCH evaluation |
| `/brand positioning <name>` | Positioning statement (Ries/Trout template) |
| `/brand ux-audit <url>` | UX heuristic audit (Nielsen 10) |
| `/brand voice <context>` | Define brand voice and tone guide |
| `/brand wireframe <page>` | UI wireframe and information architecture |

**Skills** (16 — 15 sub-skills plus the `/brand` hub):

| Skill | What it does |
| --- | --- |
| `archetype-finder` | Identifies a brand's archetype from the 12 Jungian archetypes and maps it to personality traits, voice, and... |
| `brand-hub` | Brand & Design department. Full brand identity creation, UX/UI design, design systems, visual identity, and... |
| `colors` | Designs a brand color palette — primary, secondary, accent, and neutrals — delivered with hex codes, usage... |
| `design-dna` | Extracts the design DNA of a reference UI into a structured JSON profile across three dimensions — design_s... |
| `design-review` | Visual review of live designs against brand guidelines and a named benchmark — screenshots the real UI (Pla... |
| `design-system` | Ships a production design system in 5 deliverables: design-tokens.json (primitive + semantic layers), an At... |
| `identity-system` | Builds a full brand identity in the correct order — strategy, then verbal, then visual (never skips to visu... |
| `logo-brief` | Generates logo concepts from a brief: mood references, AI-generated concept directions, variations, rationa... |
| `mockup-generate` | Generates brand-applied mockups — product, packaging, social, and stationery — with AI image-generation pro... |
| `motion-design` | Motion design direction — decides WHAT should move, how fast, and why, before any code: emotional intent, moti... |
| `naming-evaluate` | Generates 30+ brand name candidates across six categories and evaluates them with Alexandra Watkins' SMILE... |
| `positioning-statement` | Writes a brand positioning statement in the Ries/Trout format — FOR [target] WHO [need], [brand] IS A [cate... |
| `primal-audit` | Audits an existing brand against Patrick Hanlon's 7 Primal Code elements using a 21-point evidence-cited ru... |
| `ux-audit` | UX heuristic audit of a live interface against Nielsen's 10 heuristics and Laws of UX — navigates real user... |
| `voice-guide` | Creates a brand voice and tone guide — personality, vocabulary, do's and don'ts, tone matrix, and channel-s... |
| `wireframe` | Designs wireframes — layout, navigation, content hierarchy, and interaction notes — using Garrett's 5 Plane... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Valentina | Creative Director | 1 |
| Iris | Design Ops Lead | 1 |
| Mateus | Brand Strategist | 2 |
| Júlia | UX Strategist | 2 |
| Isabel | Visual Designer | 2 |
| Renata | UX Researcher | 2 |
| Sofia D. | UX/UI Designer | 2 |
| Nia | Design Extraction Engineer | 2 |
| Leo | Component Library Padronizer | 2 |
| Oren | Accessibility Auditor | 2 |

## Frameworks

- **Primal Branding — 7 Elements (Patrick Hanlon):** the underlying audit model for any brand health check
- **Brand Identity Process (Alina Wheeler):** 8-phase methodology from research through brand launch
- **12 Jungian Archetypes:** primary archetype selection with shadow and secondary mapping
- **StoryBrand SB7 (Donald Miller):** customer-as-hero narrative for all messaging work
- **Positioning (Ries / Trout):** perceptual map and differentiation framing
- **Design Thinking (IDEO):** double diamond — diverge before converging
- **Atomic Design (Brad Frost):** atoms → molecules → organisms → templates → pages
- **Nielsen's 10 Heuristics:** the evaluation standard for every UX audit
- **Laws of UX (Yablonski):** applied to interface decisions at the component level
- **Garrett's 5 Planes (strategy → surface):** structure used by Sofia D. for product design
- **Dieter Rams — less but better:** Isabel's filter for every visual decision
- **Design Tokens W3C Spec (DTCG primitive → semantic → component):** token architecture used by Iris, Nia, and Leo
- **WCAG 2.2 AA / AAA + POUR Principles:** Oren's conformance standard — non-negotiable on every component
- **ARIA Authoring Practices + Inclusive Design (Microsoft):** keyboard navigation and cognitive accessibility

## What you can ask for

- "Audit our brand against the Primal Branding framework" → `/brand primal-audit`
- "Find our brand archetype — we're between Sage and Magician" → `/brand archetype-finder`
- "Build the full brand identity from scratch — strategy through visual system" → `/brand identity-system`
- "Generate 50 name candidates and score them against SMILE & SCRATCH" → `/brand naming-evaluate`
- "Create a positioning statement for our new product line" → `/brand positioning-statement`
- "Design our color palette with contrast ratios and token spec" → `/brand colors`
- "Write the brand voice guide with do's, don'ts, and channel examples" → `/brand voice-guide`
- "Generate a logo brief and AI concept variations" → `/brand logo-brief`
- "Run a heuristic UX audit against Nielsen's 10 rules" → `/brand ux-audit`
- "Build the full design system spec with tokens and WCAG AA" → `/brand design-system`
- "Create wireframes for the onboarding flow" → `/brand wireframe`
- "Generate product mockups with the brand applied" → `/brand mockup-generate`
- "Review the current designs against brand guidelines" → `/brand design-review`

## When to use it

Use Brand & Design at the start of any product, campaign, or feature that will be seen by users — or whenever existing brand application has drifted and needs correction. The squad is also the mandatory gate before the frontend-dev squad implements any new UI: Valentina reviews and approves creative direction before Diana writes a line of component code.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
