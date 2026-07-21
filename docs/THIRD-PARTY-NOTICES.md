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
