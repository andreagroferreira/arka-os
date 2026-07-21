# Design Registers — Brand vs Product

> Derived from [impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0 — see `impeccable.LICENSE` and `impeccable.NOTICE` in this directory). Merged from upstream `brand.md` + `product.md`; reflex-reject lists relocated to the doctrine hub.

## Register selection

Pick the register before critiquing or designing, in this order:

1. **Task cue** — what the request names: "landing page", "brand site", "campaign" → brand; "dashboard", "settings", "admin", "table" → product.
2. **Surface in focus** — what the file or route actually is: a marketing route is brand even inside an app repo; an authenticated tool screen is product even on a brand domain.
3. **Project context** — the project's design system and standing brand commitments break ties and always constrain both registers.

One register per surface. Mixed products (marketing site + app) switch register per surface, not per project.

## Brand register

When design IS the product: brand sites, landing pages, marketing surfaces, campaign pages, portfolios, long-form content, about pages. The deliverable is the design itself; a visitor's impression is the thing being made.

The register spans every genre. A tech brand (Stripe, Linear, Vercel). A luxury brand (a hotel, a fashion house). A consumer product (a restaurant, a travel site, a CPG packaging page). A creative studio, an agency portfolio, a band's album page. They all share the stance (*communicate, not transact*) and diverge wildly in aesthetic. Don't collapse them into a single look.

### The brand slop test

If someone could look at this and say "AI made that" without hesitation, it's failed. The bar is distinctiveness; a visitor should ask "how was this made?", not "which AI made this?"

Brand isn't a neutral register. AI-generated landing pages have flooded the internet, and average is no longer findable. Restraint without intent now reads as mediocre, not refined. Brand surfaces need a POV, a specific audience, a willingness to risk strangeness. Go big or go home.

**The second slop test: aesthetic lane.** Before committing to moves, name the reference. A Klim-style specimen page is one lane; Stripe-minimal is another; Liquid-Death-acid-maximalism is another. Don't drift into editorial-magazine aesthetics on a brief that isn't editorial. A hiking brand with Cormorant italic drop caps has the wrong register within the register.

Then the inverse test: in one sentence, describe what you're about to build the way a competitor would describe theirs. If that sentence fits the modal landing page in the category, restart.

### Typography

#### Font selection procedure

Every project. Never skip. <!-- rule:brand-typo-font-selection-procedure -->

1. Read the brief. Write three concrete brand-voice words. Not "modern" or "elegant," but "warm and mechanical and opinionated" or "calm and clinical and careful." Physical-object words.
2. List the three fonts you'd reach for by reflex. If any appear in the reflex-reject list below, reject them; they are training-data defaults and they create monoculture.
3. Browse a real catalog (Google Fonts, Pangram Pangram, Future Fonts, Adobe Fonts, ABC Dinamo, Klim, Velvetyne) with the three words in mind. Find the font for the brand as a *physical object*: a museum caption, a 1970s terminal manual, a fabric label, a cheap-newsprint children's book, a concert poster, a receipt from a mid-century diner. Reject the first thing that "looks designy."
4. Cross-check. "Elegant" is not necessarily serif. "Technical" is not necessarily sans. "Warm" is not Fraunces. If the final pick lines up with the original reflex, start over.

#### Reflex-reject list

<!-- rule:brand-typo-reflex-reject-fonts -->

The canonical reflex-reject list (fonts + aesthetic lanes) lives in `departments/brand/references/uiux-knowledge-and-tools.md` §11. The identity-preservation carve-out applies: existing brand commitments always win over the ban list.

#### Reflex-reject aesthetic lanes

Parallel to the font list. Currently saturated aesthetic families that have flooded brand surfaces. If a brief lands in one of these lanes without a register reason that *requires* it (a literal magazine, a literal terminal, a literal industrial signage system), it's the second-order training reflex: the trap one tier deeper than picking a Fraunces font. Look further. <!-- rule:brand-typo-reflex-reject-lanes -->

The canonical reflex-reject list (fonts + aesthetic lanes) lives in `departments/brand/references/uiux-knowledge-and-tools.md` §11. The identity-preservation carve-out applies: existing brand commitments always win over the ban list.

The reflex-reject lists apply to **new design choices**. When the existing brand has already committed to a font or a lane as part of its identity, identity-preservation wins; variants on an existing surface don't second-guess what's already shipping. The reflex-reject lists are for greenfield decisions and for departure-mode variants.

#### Pairing and voice

Distinctive + refined is the goal. The specific shape depends on the brand, not on the brand's category. A category ("restaurant", "dev tool", "magazine", "fintech") is not a recipe; treating it as one is the first-order reflex the doctrine warns against. <!-- rule:brand-typo-pairing-voice -->

Two families minimum is the rule *only* when the voice needs it. A single well-chosen family with committed weight/size contrast is stronger than a timid display+body pair.

#### Scale

Modular scale, fluid `clamp()` for headings, ≥1.25 ratio between steps. Flat scales (1.1× apart) read as uncommitted. <!-- rule:brand-typo-modular-scale -->

Light text on dark backgrounds: add 0.05–0.1 to line-height. Light type reads as lighter weight and needs more breathing room. <!-- rule:brand-typo-light-on-dark-leading -->

### Color

Brand surfaces have permission for Committed, Full palette, and Drenched strategies. Use them. A single saturated color spread across a hero is not excess; it's voice. A beige-and-muted-slate landing page ignores the register. <!-- rule:brand-color-strategy-permission -->

- Name a real reference before picking a strategy. "Klim Type Foundry #ff4500 orange drench", "Stripe purple-on-white restraint", "Liquid Death acid-green full palette", "Mailchimp yellow full palette", "Condé Nast Traveler muted navy restraint", "Vercel pure black monochrome". Unnamed ambition becomes beige. <!-- rule:brand-color-named-reference -->
- Palette IS voice. A calm brand and a restless brand should not share palette mechanics. <!-- rule:brand-color-palette-is-voice -->
- When the strategy is Committed or Drenched, color carries the brand. Don't hedge with neutrals around the edges. Commit. <!-- rule:brand-color-commit-no-hedge -->
- Don't converge across projects. Each brand surface differentiates from the last. <!-- rule:brand-color-no-converge -->
- When a cultural-symbol palette is the obvious pull, reach past it. Let the cultural reading come from typography, imagery, and copy, not the palette. <!-- rule:brand-color-no-cultural-symbol -->

### Layout

- Asymmetric compositions are one option. Break the grid intentionally for emphasis. <!-- rule:brand-layout-asymmetric -->
- Fluid spacing with `clamp()` that breathes on larger viewports. Vary for rhythm: generous separations, tight groupings. <!-- rule:brand-layout-fluid-spacing -->
- For image-led briefs (hotels, restaurants, magazines, photography), full-bleed hero imagery with overlaid menu and centered headline is a canonical move; let the photograph be the design. <!-- rule:brand-layout-image-led-hero -->
- When cards ARE the right affordance, use `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` for breakpoint-free responsiveness. <!-- rule:brand-layout-cards-when-right -->

### Imagery

Brand surfaces lean on imagery. A restaurant, hotel, magazine, or product landing page without any imagery reads as incomplete, not as restrained. A solid-color rectangle where a hero image should go is worse than a representative stock photo.

**When the brief implies imagery, you must ship imagery.** Zero images is a bug, not a design choice. "Restraint" is not an excuse. If the approved comp or brief is image-led, ship real project assets, generated raster assets, or a credible canvas/SVG/WebGL scene. Do not replace photographic, architectural, product, or place imagery with generic CSS panels, decorative diagrams, cards, bullets, or copy. <!-- rule:brand-imagery-required -->

- **For greenfield work without local assets, use stock imagery.** Unsplash is the default. The URL shape is `https://images.unsplash.com/photo-{id}?auto=format&fit=crop&w=1600&q=80`. **Verify the URLs before referencing them.** If you have an image-search MCP, web-fetch tool, or browser access, use it to find real photo IDs and confirm they resolve. Guessed IDs (even ones that look real) often 404 and ship as broken-image placeholders. Without a verification path, pick fewer photos you're confident exist over more that you guessed; never substitute colored `<div>` placeholders. <!-- rule:brand-imagery-unsplash-default -->
- **Search for the brand's physical object**, not the generic category: "handmade pasta on a scratched wooden table" beats "Italian food"; "cypress trees above a limestone hotel facade at dusk" beats "luxury hotel". <!-- rule:brand-imagery-physical-object-search -->
- **One decisive photo beats five mediocre ones.** Hero imagery should commit to a mood; padding with more stock doesn't rescue an indecisive one. <!-- rule:brand-imagery-one-decisive-photo -->
- **Alt text is part of the voice.** "Coastal fettuccine, hand-cut, served on the terrace" beats "pasta dish". <!-- rule:brand-imagery-alt-text -->

"Imagery" here is broader than stock photography: product screenshots, custom data visualizations, generated SVG, and canvas/WebGL scenes are all imagery. Text-only pages where typography alone carries the entire visual weight are the failure mode.

### Motion

- One well-orchestrated page-load beats scattered micro-interactions, when the brand invites it. Some brands skip entrance motion entirely; the restraint is the voice. <!-- rule:brand-motion-one-page-load -->

### Brand bans (on top of the shared absolute bans)

- Monospace as lazy shorthand for "technical / developer." If the brand isn't technical, mono reads as costume. <!-- rule:brand-ban-mono-as-shorthand -->
- Large rounded-corner icons above every heading. Screams template. <!-- rule:brand-ban-large-rounded-icons -->
- Single-family pages that picked the family by reflex, not voice. (A single family chosen deliberately is fine.) <!-- rule:brand-ban-single-family-by-reflex -->
- All-caps body copy. Reserve caps for short labels and headings. <!-- rule:brand-ban-all-caps-body -->
- Timid palettes and average layouts. Safe = invisible. <!-- rule:brand-ban-timid-palettes -->
- Zero imagery on a brief that implies imagery (restaurant, hotel, food, travel, fashion, photography, hobbyist). Colored blocks where a hero photo belongs. <!-- rule:brand-ban-zero-imagery -->
- Defaulting to editorial-magazine aesthetics (display serif + italic + drop caps + broadsheet grid) on briefs that aren't magazine-shaped. Editorial is ONE aesthetic lane, not the default brand aesthetic. <!-- rule:brand-ban-editorial-default -->
- Repeated tiny uppercase tracked labels above every section heading. A single strong kicker can be voice; repeating it as section grammar is AI scaffolding unless it's a deliberate, named brand system. <!-- rule:brand-ban-repeated-section-kickers -->

### Brand permissions

Brand can afford things product can't. Take them.

- Ambitious first-load motion. Reveals and typographic choreography that earn their place; not fade-on-scroll for every section. <!-- rule:brand-permission-first-load-motion -->
- Single-purpose viewports. One dominant idea per fold, long scroll, deliberate pacing. <!-- rule:brand-permission-single-purpose-viewports -->
- Unexpected color strategies. Palette IS voice; a calm brand and a restless brand should not share palette mechanics. <!-- rule:brand-permission-unexpected-color -->
- Art direction per section. Different sections can have different visual worlds if the narrative demands it. Consistency of voice beats consistency of treatment. <!-- rule:brand-permission-art-direction -->

## Product register

When design SERVES the product: app UIs, admin dashboards, settings panels, data tables, tools, authenticated surfaces, anything where the user is in a task.

### The product slop test

Not "would someone say AI made this." Familiarity is often a feature here. The test is: would a user fluent in the category's best tools (Linear, Figma, Notion, Raycast, Stripe come to mind) sit down and trust this interface, or pause at every subtly-off component?

Product UI's failure mode isn't flatness, it's strangeness without purpose: over-decorated buttons, mismatched form controls, gratuitous motion, display fonts where labels should be, invented affordances for standard tasks. The bar is earned familiarity. The tool should disappear into the task.

### Typography

- **One family is often right.** Product UIs don't need display/body pairing. A well-tuned sans carries headings, buttons, labels, body, data. <!-- rule:product-typo-one-family -->
- **Fixed rem scale, not fluid.** Clamp-sized headings don't serve product UI. Users view at consistent DPI, and a fluid h1 that shrinks in a sidebar looks worse, not better. <!-- rule:product-typo-fixed-rem-scale -->
- **Tighter scale ratio.** 1.125–1.2 between steps is typical. More type elements here than on brand surfaces; exaggerated contrast creates noise. <!-- rule:product-typo-tighter-ratio -->
- **Line length still applies for prose** (65–75ch). Data and compact UI can run denser; tables at 120ch+ are fine. <!-- rule:product-typo-line-length -->

### Color

Product defaults to Restrained. A single surface can earn Committed (a dashboard where one category color carries a report, an onboarding flow with a drenched welcome screen), but Restrained is the floor. <!-- rule:product-color-restrained-default -->

- State-rich semantic vocabulary: hover, focus, active, disabled, selected, loading, error, warning, success, info. Standardize these. <!-- rule:product-color-state-vocab -->
- Accent color used for primary actions, current selection, and state indicators only, not decoration. <!-- rule:product-color-accent-only -->
- A second neutral layer for sidebars, toolbars, and panels (slightly cooler or warmer than the content surface). <!-- rule:product-color-second-neutral -->

### Layout

- Responsive behavior is structural (collapse sidebar, responsive table, breakpoint-driven columns), not fluid typography. <!-- rule:product-layout-responsive-structural -->

### Components

Every interactive component has: default, hover, focus, active, disabled, loading, error. Don't ship with half of these. <!-- rule:product-components-all-states -->

- Skeleton states for loading, not spinners in the middle of content. <!-- rule:product-components-skeleton-loading -->
- Empty states that teach the interface, not "nothing here." <!-- rule:product-components-empty-states -->
- Consistent affordances across the surface. Same button shape. Same form-control vocabulary. Same icon style. <!-- rule:product-components-consistent-affordances -->

### Motion

- 150–250 ms on most transitions. Users are in flow; don't make them wait for choreography. <!-- rule:product-motion-quick-transitions -->
- Motion conveys state, not decoration. State change, feedback, loading, reveal: nothing else. <!-- rule:product-motion-state-not-decoration -->
- No orchestrated page-load sequences. Product loads into a task; users don't want to watch it load. <!-- rule:product-motion-no-page-load-sequence -->

### Product bans (on top of the shared absolute bans)

- Decorative motion that doesn't convey state. <!-- rule:product-ban-decorative-motion -->
- Inconsistent component vocabulary across screens. If the "save" button looks different in two places, one is wrong. <!-- rule:product-ban-inconsistent-components -->
- Display fonts in UI labels, buttons, data. <!-- rule:product-ban-display-fonts-ui -->
- Reinventing standard affordances for flavor (custom scrollbars, weird form controls, non-standard modals). <!-- rule:product-ban-reinvented-affordances -->
- Heavy color or full-saturation accents on inactive states. <!-- rule:product-ban-heavy-inactive-color -->
- Modal as first thought. Modals are usually laziness. Exhaust inline / progressive alternatives first. <!-- rule:product-ban-modal-first-thought -->

### Product permissions

Product can afford things brand surfaces can't.

- System fonts and familiar sans defaults (Inter, SF Pro, system-ui stacks).
- Standard navigation patterns: top bar + side nav, breadcrumbs, tabs, command palettes.
- Density. Tables with many rows, panels with many labels, dense information when users need it.
- Consistency over surprise. The same visual vocabulary screen to screen is a virtue; delight is saved for moments, not pages.
