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
