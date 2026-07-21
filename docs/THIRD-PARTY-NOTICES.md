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

Material derived from this project (this table lists only what has
actually landed; rows are added by the PR that ships each surface):

| Surface | Location | Notes |
|---|---|---|
| Marketing tools tree | `departments/marketing/tools/` | Integration guides (`integrations/`), zero-dependency CLI wrappers (`clis/`), Composio layer (`composio/`), `REGISTRY.md` — imported with tree-internal links preserved |

Upstream promotional links and sponsor references were removed during
import; framework content, references, and tool guides were preserved
and adapted. The MIT permission notice and copyright line above apply to
all copies and substantial portions of the derived material.

Later phases of the integration will add rows here as they land the
corresponding surfaces — imported skills (`metadata.origin: community`),
enriched first-party skills (`derived:` in
`config/skills-provenance.yaml`), and converted eval cases.
