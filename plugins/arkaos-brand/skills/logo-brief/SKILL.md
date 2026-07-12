---
name: logo-brief
description: >
  Generates logo concepts from a brief: mood references, AI-generated concept
  directions, variations, rationale, and usage guidelines. TRIGGER: "logo
  brief", "cria um logo", "desenha o logótipo", "logo concepts", "preciso de
  um logo", "/brand logo <brief>". SKIP: logo as part of a whole identity
  (strategy + verbal + visual) -> brand/identity-system (order matters, the
  logo comes last); applying an existing logo to product, packaging, or social
  scenes -> brand/mockup-generate.
---

# Logo

> **Agent:** Isabel (Visual Designer) | **Framework:** Logo Design Principles + AI Generation
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE any concept work, in this order, and record what actually
loaded:

1. **`Skill(frontend-design)`** — anti-default doctrine: distinctive
   marks come from the brand's own world; one aesthetic risk, justified.
2. **`Skill(ui-ux-pro-max)`** — typography data (57 pairings) for
   wordmark craft and lockup type decisions.
3. **Read the brand strategy** — positioning/archetype from the
   identity work; a logo brief without strategy input gets sent back to
   `brand/identity-system`.

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company whose mark discipline this logo should be
judged against (FedEx for hidden meaning, Chanel for reduction, Stripe
for geometric warmth…), and state what that company's design lead would
reject in your current directions.

## Anti-default check

AI-logo defaults: generic geometric animal, gradient hexagon/orbit,
lowercase-sans-with-one-colored-letter. §8 self-test on every direction:
*"would this exact mark appear for any other company?"* A mark must
survive one-color, 16px favicon, and embroidery.

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE the first Write/Edit. Full contract: §9 of
the squad reference.

## Workflow

1. **Brief decomposition** — what the brand does, for whom, archetype,
   one word the mark must communicate, contexts (app icon? signage?
   embroidery?).
2. **Mood references** — 3–5 references from the brand's OWN world
   (materials, tools, geography), each with one line on what to steal
   and what to refuse.
3. **Three concept directions** — one wordmark, one monogram/lettermark,
   one symbol/abstract; for each: sketch description, construction notes
   (grid, stroke, negative space), rationale tied to strategy, and the
   §8 self-test verdict.
4. **Generation prompts** — engine-ready prompts per direction (flat
   vector language, one-color first, exact hexes only after form is
   locked). Higgsfield MCP (`generate_image`) is the primary backend
   when connected; any capable generator works from the same prompts.
5. **Variations grid** — for the recommended direction: horizontal /
   stacked / icon-only lockups, one-color, reversed, min sizes.
6. **Usage guidelines** — clear space (in units of the mark), min size
   px/mm, forbidden treatments (§4 motion bans apply to animated use).

## Output

| Deliverable | Format |
|---|---|
| 3 concept directions | sketch + construction + rationale + self-test |
| Recommendation | winner + why the losers lost |
| Prompt set | engine-ready generation prompts per direction |
| Variations grid | lockups, one-color, reversed, min sizes |
| Usage guide | clear space, min size, forbidden treatments |

Saved to Obsidian under the project's Brand path; feeds
`brand/mockup-generate` for application scenes.

## Examples

```
/brand logo "CLI-first agent OS, precision + calm authority"
/brand logo "artisan coffee roaster, heat + patience as materials"
/brand logo "pediatric clinic, trust without infantilization"
```
