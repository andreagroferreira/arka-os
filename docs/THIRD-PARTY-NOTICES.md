# Third-Party Notices

ArkaOS incorporates material derived from third-party open-source
projects. This file is the single index of those origins; the
authoritative per-skill classification lives in
`config/skills-provenance.yaml` (`derived:` section) and in each skill's
frontmatter `metadata: {origin, source, license}` block, enforced by
`tests/python/test_skill_provenance.py`.

## marketing-skills (Corey Haines)

- **Source:** https://github.com/coreyhaines31/marketingskills
- **License:** MIT — Copyright (c) 2025 Corey Haines
- **License text:** retained verbatim at
  `departments/marketing/tools/LICENSE`

Material derived from this project:

| Surface | Location | Notes |
|---|---|---|
| Marketing tools tree | `departments/marketing/tools/` | Integration guides (`integrations/`), zero-dependency CLI wrappers (`clis/`), Composio layer (`composio/`), `REGISTRY.md` — imported with tree-internal links preserved |
| Imported skills | department `SKILL.md` files declaring `metadata.origin: community` | 27 new skills + 20 enriched existing skills, adapted to the ArkaOS skill standard (routing, KB-first, agent bindings); the authoritative per-skill list is `config/skills-provenance.yaml` under `derived:` |
| Eval corpus | `config/evals/*.yaml`, entries tagged `imported` | 291 cases converted from the upstream `evals/evals.json` files by `scripts/tools/evals_import.py` |

Upstream promotional links and sponsor references were removed during
import; framework content, references, and tool guides were preserved
and adapted. The MIT permission notice and copyright line above apply to
all copies and substantial portions of the derived material.

## stop-slop (Hardik Pandya)

- **Source:** https://github.com/hardikpandya/stop-slop
- **License:** MIT — Copyright (c) 2025 Hardik Pandya
- **License text:** retained verbatim at
  `arka/skills/human-writing/references/stop-slop.LICENSE`

Material derived from this project:

| Surface | Location | Notes |
|---|---|---|
| Structural anti-slop catalogue | `arka/skills/human-writing/references/structural-patterns.md` | Near-verbatim port of upstream `references/structures.md` plus selected before/after examples; one upstream example fixed (em dash removed per Rule 1) |
| Phrase anti-slop catalogue | `arka/skills/human-writing/references/anti-slop-phrases.md` | Upstream `references/phrases.md` deduplicated against the constitution `no-ai-cliches` list and `forbidden-patterns.md`; adverb rule softened to "cut by default" |
| Skill sections | `arka/skills/human-writing/SKILL.md` | Rule 8 (No Formulaic Structures), structural sweep in Quick-Pass Checks, and the 5-dimension Slop Score rubric (revise below 35/50) |

Dual-source note: `arka/skills/human-writing` was first derived from
marketing-skills (section above), and its frontmatter `metadata.source`
names that primary source — the provenance schema records one source per
skill. This section is the authoritative record of the second source.
The MIT permission notice and copyright line above apply to all copies
and substantial portions of the derived material.

## hallmark (Hassan El Mghari / "Hallmark contributors")

- **Source:** https://github.com/nutlope/hallmark
- **License:** MIT — Copyright (c) 2026 Hallmark contributors
- **License text:** retained verbatim at
  `departments/brand/skills/design-review/references/hallmark.LICENSE`
- **Upstream version:** v1.1.0 (main HEAD `aeb42fb`, 2026-06-04)

Material derived from this project:

| Surface | Location | Notes |
|---|---|---|
| Slop-test gates | `departments/brand/skills/design-review/references/slop-test.md` | Near-verbatim port of the 58 pass/fail gates + six-axis pre-emit critique (P/H/E/S/R/V) |
| Anti-pattern dictionary | `departments/brand/skills/design-review/references/anti-patterns.md` | Named AI tells with severity tiers and the audit report format; image-generation recommendations repointed to the ArkaOS image pipeline |
| Genre references | `departments/brand/skills/design-review/references/genres/` | editorial, modern-minimal, atmospheric, playful |
| Font ban list (merged) | `departments/brand/references/uiux-knowledge-and-tools.md` §11 | Union with the impeccable reflex-reject list, deduplicated; carve-out semantics preserved |
| Pre-emit critique protocol | `departments/brand/references/uiux-knowledge-and-tools.md` §8 | Six-axis scoring + `[arka:design-dna]` stamp (§9), renamed from the upstream `Hallmark ·` stamp |
| Skill sections | `departments/brand/skills/design-review/SKILL.md`, `departments/brand/skills/ux-audit/SKILL.md` | Slop-gates pre-verdict step, audit flow (pre-flight scan, severity report format), redesign boundaries in `arka/skills/refine/SKILL.md` |
| Macrostructures (W2) | `departments/landing/skills/page-architect/references/macrostructures.md` + `macrostructures/` (21 files) | Near-verbatim; diversification rule reads the `[arka:design-dna]` stamp and `.arka/design/log.json` |
| Component cookbook (W2) | `departments/landing/skills/page-architect/references/component-cookbook.md` + `components/` (50 files) | Near-verbatim; example footer strings replaced with neutral fictional content |
| Hero enrichment + nav recipe (W2) | `departments/landing/skills/page-architect/references/hero-enrichment.md`, `floating-nav.md` | Hosted imagery kit and external image-gen services repointed to the ArkaOS image pipeline |
| Layout/copy craft (W2, merged) | `departments/landing/skills/page-architect/references/layout-craft.md`, `ui-copy.md` | Merged with impeccable layout material (see impeccable section); prose-tone rules deferred to `arka/skills/human-writing` |
| Design DNA study (W2) | `departments/brand/skills/design-system/references/design-dna-study.md` | SSRF-safety, refusal layer, prompt-injection handling and attestation gate kept byte-identical |
| design.md spec + exports (W2) | `departments/brand/skills/design-system/references/design-md-spec.md` | Merged from upstream `design-md.md` + `export-formats.md`; ArkaOS `design-system.yaml` bridge added |
| Typography/interaction craft (W2, merged) | `departments/brand/skills/design-system/references/typography-craft.md`, `interaction-states.md` | Merged with impeccable typeset/interaction material; ban lists relocated to doctrine hub §11 |
| Theme specs (W2) | `departments/brand/skills/design-system/references/themes/` (4 files) | carnival, cobalt, hum, lumen — opt-in seeds, catalogued in doctrine hub §10 |
| OKLCH theme construction (W2, merged) | `departments/brand/skills/colors/references/oklch-theme.md` | hallmark algorithm as spine, impeccable colorize rules folded in |
| Motion recipes (W2, merged) | `departments/dev/skills/animated-website/references/motion-recipes.md` | 15 recipes + 20 tells mapped onto the doctrine hub §4 timing tokens (hub wins on conflicts) |

Changes on import: "Powered by Together AI" sponsor references removed;
the `Hallmark ·` CSS stamp namespace renamed to `[arka:design-dna]`;
`.hallmark/log.json` project memory relocated to `.arka/design/log.json`;
external image-generation service recommendations repointed to the
ArkaOS image pipeline; the personal talk deck (`docs/talk-slides.md`)
and the `usehallmark.com` hosted imagery kit were not imported. The MIT
permission notice and copyright line above apply to all copies and
substantial portions of the derived material.

## impeccable (Paul Bakaus)

- **Source:** https://github.com/pbakaus/impeccable
- **License:** Apache License 2.0 — Copyright Paul Bakaus
- **License text:** retained verbatim at
  `departments/brand/skills/design-review/references/impeccable.LICENSE`
- **NOTICE:** carried verbatim at
  `departments/brand/skills/design-review/references/impeccable.NOTICE`
  (Apache License §4(d))
- **Upstream version:** HEAD `4d849eb` (2026-07-21); npm CLI `impeccable` v3.2.x

First Apache-2.0 absorption in this repo. Statement of changes, as the
license requires:

| Surface | Location | Notes / changes made |
|---|---|---|
| Design registers (brand vs product) | `departments/brand/skills/design-review/references/design-registers.md` | Merged from upstream `skill/reference/brand.md` + `product.md`; reflex-reject list bodies relocated to the doctrine hub §11 (pointers left in place); `{{template}}` tokens removed; upstream `<!-- rule:... -->` IDs preserved |
| Critique protocol | `departments/brand/skills/design-review/references/critique-protocol.md` | Substantial distillation of upstream `skill/reference/critique.md` (819 → ~170 lines): two-isolated-subagent orchestration, blind scoring, P0–P3 severity, personas and honesty rubric kept; CLI/session/live-mode plumbing and inline Nielsen-10 textbook material removed |
| Design laws | `departments/brand/references/uiux-knowledge-and-tools.md` §12 | Compacted from upstream `skill/SKILL.src.md` general rules + absolute bans; provider-conditional blocks resolved |
| Font + lane ban list (merged) | `departments/brand/references/uiux-knowledge-and-tools.md` §11 | Union with the hallmark banned-defaults list, deduplicated |
| Design detector | external npm CLI `impeccable`, shelled by the QG check `design-slop` (Wave 3) | Dependency only — no upstream code vendored |
| Layout craft (W2, merged) | `departments/landing/skills/page-architect/references/layout-craft.md` | Upstream `skill/reference/layout.md` folded into the hallmark layout/responsive merge (optical adjustments, hierarchy table, squint test) |
| Typography/interaction craft (W2, merged) | `departments/brand/skills/design-system/references/typography-craft.md`, `interaction-states.md` | Upstream `typeset.md` (rem-vs-clamp doctrine, font-loading mechanics, dark-bg compensation) and `interaction-design.md` (dropdown clipping, anchor positioning) folded into the hallmark merges |
| OKLCH color rules (W2, merged) | `departments/brand/skills/colors/references/oklch-theme.md` | Upstream `colorize.md` rules (HSL→OKLCH rationale, tinted neutrals, alpha smell, dark-mode table) folded into the hallmark algorithm |
| Motion craft (W2, merged) | `departments/dev/skills/animated-website/references/motion-recipes.md` | Upstream `animate.md` (easing beziers, exits-75%, materials palette, 80ms threshold) folded in; doctrine hub §4 tokens win on conflicts |

Not imported: `skill/reference/ios.md` and `skill/reference/android.md`
(MIT-derived from ehmo/platform-design-skills per the upstream NOTICE —
deliberately excluded to avoid a third attribution chain), the upstream
`DESIGN.md`/`PRODUCT.md` brand artifacts (Impeccable's own identity),
and all JavaScript (detector engine, live mode, hooks, build system).
`impeccable.style` self-references, `IMPECCABLE_*` environment variables
and command-router plumbing were removed from ported prose.

Dual-source note: `departments/brand/skills/design-review` is primarily
derived from hallmark (its frontmatter `metadata.source` names it — the
provenance schema records one source per skill); this section is the
authoritative record of the impeccable-derived material inside the same
skill directory and the doctrine hub.
