---
name: mockup-generate
description: >
  Generates brand-applied mockups — product, packaging, social, and stationery
  — with AI image-generation prompts and brand application guidelines.
  TRIGGER: "cria mockups", "mockup do produto", "packaging mockup", "aplica a
  marca no produto", "social media mockup", "/brand mockup <type>". SKIP:
  low-fidelity screen structure and layout -> brand/wireframe (structure
  before pixels); creating the logo itself -> brand/logo-brief (concepts, not
  application).
---

# Mockup

> **Agent:** Isabel (Visual Designer) | **Framework:** AI Image Generation + Brand Application
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE writing a single generation prompt, in this order, and
record what actually loaded:

1. **`Skill(frontend-design)`** — anti-default doctrine: the subject's
   own world (materials, instruments, vernacular) is where distinctive
   scenes come from, not stock-photo tropes.
2. **`Skill(ui-ux-pro-max)`** — palette/typography data to keep brand
   fidelity checkable in the generated output.
3. **Read the brand identity source** — brandbook, `design-system.yaml`,
   or logo package; §3 of the squad reference as in-repo fallback. A
   mockup without the real tokens is fan-art, not brand application.

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company whose product/packaging photography this
mockup set should be judged against (Apple for product staging, Aesop
for material honesty, Notion for illustration-led social…), and state
what that company's design lead would reject in your current scenes.

## Anti-default check

Generic mockup defaults: floating device on gradient, laptop-on-desk
with latte, gold-foil-on-black packaging. Use §8's self-test — *"would
this exact scene appear for any other brand?"* — and pull the scene from
the brand's actual world instead.

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE the first Write/Edit. Full contract: §9 of
the squad reference.

## Workflow

1. **KB + identity** — pull the real brand tokens (palette hexes, type,
   logo variants, clear-space rules) and cite the source note. All
   generated imagery runs through the ArkaOS image pipeline
   (`/brand image-create`, ComfyUI) — never external one-off image
   services.
2. **Scene selection** — per requested type (product / packaging /
   social / stationery), design 2–3 scenes rooted in the brand's world;
   one sentence of rationale each.
3. **Prompt engineering** — one generation prompt per scene specifying:
   subject + environment, camera (focal length, angle), lighting setup,
   material vernacular, exact brand hexes, logo placement + clear space,
   aspect ratio per destination (1:1, 4:5, 16:9, 9:16), and negative
   space reserved for copy. Name the intended engine — the Higgsfield
   MCP (`generate_image`; `remove_background`/`upscale_image` for
   post) is the primary backend when connected; any capable generator
   works from the same prompt set.
4. **Brand application rules** — for each scene: logo min-size,
   clear space, color fidelity tolerance, type-in-image rules.
5. **Fidelity pass** — after generation, check output against tokens
   (palette drift, logo distortion, off-brand materials) and regenerate
   or post-process what fails; state what was rejected and why.

## Output

| Deliverable | Format |
|---|---|
| Scene set | 2–3 scenes per type with rationale |
| Prompt set | engine-ready prompts (subject/camera/light/brand tokens) |
| Application guide | logo, clear space, color fidelity, type rules |
| Fidelity report | what was rejected/regenerated and why |

Saved to Obsidian under the project's Brand path; images land in the
project's assets dir with the marker's `tokens=` naming their source.

## Examples

```
/brand mockup product      # hero product shots in the brand's world
/brand mockup packaging    # box/label scenes, material-honest
/brand mockup social       # per-platform templates (1:1, 4:5, 9:16)
/brand mockup stationery   # cards, letterhead, swag
```
