---
name: brand/identity-system
description: >
  Builds a full brand identity in the correct order — strategy, then verbal,
  then visual (never skips to visuals) — via the Wheeler process and Primal
  Branding, verifying live brand elements through browser and Computer Use
  steps. TRIGGER: "cria a identidade da marca", "brand identity", "identidade
  visual completa", "rebranding completo", "build the brand from scratch",
  "/brand identity <name>". SKIP: only a logo -> brand/logo-brief; only
  positioning -> brand/positioning-statement; measuring an EXISTING brand's
  strength -> brand/primal-audit (audit, not creation).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Identity System — `/brand identity <name>`

> **Agent:** Valentina (Creative Director) | **Framework:** Wheeler Process + Primal Branding
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE any identity work, in this order, and record what
actually loaded:

1. **`Skill(frontend-design)`** — anti-default doctrine; the visual
   phase of this skill lives or dies by it.
2. **`Skill(ui-ux-pro-max)`** — 161 palettes + 57 font pairings as
   comparative evidence for the visual phase; never as a pick-list.
3. **Aesthetic direction seed (optional)** — when the brand has no
   visual history, consider a curated TypeUI direction
   (`npx typeui.sh pull <slug>`, §10 of the squad reference) as a SEED
   for the token system, never as the final system.

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company whose brand coherence this identity should be
judged against (Stripe for system discipline, Apple for reduction,
Mailchimp for voice…), and state what that company's brand director
would reject in your current direction.

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE the first Write/Edit. Full contract: §9 of
the squad reference.

## Workflow (Wheeler order — never skip to visuals)

1. **Strategy** — audience, positioning, archetype, competitive frame;
   Primal Branding's 7 assets (creation story, creed, icons, rituals,
   lexicon, non-believers, leader) drafted as one-liners. Route deep
   positioning to `brand/positioning-statement` when it deserves it.
2. **Verbal** — name rationale (if naming), tagline, voice: 3 traits
   with a do/don't pair each, lexicon (words the brand owns, words it
   never uses). Verbal LOCKS before pixels.
3. **Visual** — only now. Run the §8 token-plan-then-critique loop:
   palette (4–6 named hexes via `brand/colors` discipline), type pairing
   (display/body/utility), logo direction (route execution to
   `brand/logo-brief`), iconography style, layout grammar, and the ONE
   signature element the identity is remembered by. Self-test every
   choice: *"would this appear for any other brand?"*
4. **System** — assemble tokens into a handoff for
   `brand/design-system` (DTCG-shaped), plus usage rules (clear space,
   min sizes, forbidden treatments).
5. **Verification** — check the live surfaces against the system.

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the website/app and verify brand elements match the identity system (colors, typography, spacing)
- [BROWSER] Compare generated assets side-by-side with the live site
- [BROWSER] Check favicon, og:image, and meta branding elements

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Open design tools (Figma, Canva desktop, Sketch) to verify brand assets match guidelines

## Output

Complete brand identity package saved to Obsidian, in Wheeler order:

| Phase | Deliverable |
|---|---|
| Strategy | positioning + archetype + Primal 7 assets |
| Verbal | name rationale, tagline, voice traits, lexicon |
| Visual | palette, type, logo direction, icon style, signature |
| System | DTCG token handoff + usage rules → `brand/design-system` |
