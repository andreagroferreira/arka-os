---
name: arka-design-ops
description: >
  Brand Design Ops sub-squad orchestrator — routes design-system token
  extraction, WCAG 2.2 AA audits, and shadcn/ui padronisation to Iris
  (lead), Nia (extraction), Oren (WCAG), Leo (shadcn); outputs DTCG token
  JSON, conformance reports, and canonical components. TRIGGER: "/brand
  design-ops" (extract, wcag, shadcn, audit), "extrai os design tokens
  deste site", "auditoria de acessibilidade", "WCAG audit", "padroniza
  este componente shadcn", "tokens drift audit". SKIP: brand strategy or
  visual-direction taste calls -> /brand (Valentina owns strategy, Iris
  escalates to her); implementing the resulting components in product
  code -> /dev via Paulo (design-ops produces specs/tokens/audits, never
  opens PRs).
allowed-tools: [Read, Write, Bash, Edit]
---

# /brand design-ops — Design Ops sub-squad

> Sub-squad of `/brand` (Valentina). Operational specialists for the
> production rails of design systems: tokens, audits, components.

## Squad

| Agent | Role | Tier | Owns |
| --- | --- | --- | --- |
| **Iris** (`design-ops-lead`) | Lead | 1 | governance, escalation to Valentina |
| **Nia** (`extraction-script-writer`) | Specialist | 2 | reverse-engineer tokens from sites / figma |
| **Oren** (`wcag-auditor`) | Specialist | 2 | WCAG 2.2 AA conformance + reports |
| **Leo** (`shadcn-padronizer`) | Specialist | 2 | shadcn/ui canonical components |

## Subcommands

| Command | Owner | What it does |
| --- | --- | --- |
| `/brand design-ops extract <url>` | Nia | Extract color, typography, spacing tokens from a live URL or figma file. Writes JSON to `~/.arkaos/design-ops/<slug>/tokens.json`. |
| `/brand design-ops wcag <url\|path>` | Oren | Run WCAG 2.2 AA audit. Outputs issue table (severity / criterion / location / fix) + conformance score. |
| `/brand design-ops shadcn <component>` | Leo | Generate or refactor a component to the shadcn/ui canonical form (CVA variants, Radix primitives, theme tokens). |
| `/brand design-ops audit <project>` | Iris | Orchestrate full audit: tokens drift, WCAG conformance, component-library variance. Produces a single report. |

## Scripts (under `scripts/`)

The scripts library is intentionally small at v2.27.0 — three reference
implementations to anchor the pattern. Nia / Oren / Leo extend it as
ArkaOS evolves; AIOX's reference set is ~30 scripts and ArkaOS will
catch up incrementally.

| Script | Owner | Input | Output |
| --- | --- | --- | --- |
| `scripts/extract-colors.py` | Nia | URL or local HTML | `colors.json` (DTCG-compliant token list) |
| `scripts/wcag-contrast.py` | Oren | hex pairs OR CSS file | Issue list with contrast ratios + AA / AAA verdict |
| `scripts/shadcn-tokens.py` | Leo | tokens.json | shadcn CSS variables block + Tailwind config snippet |

Run any script with `python3 scripts/<name>.py --help` for usage.

## Output

All design-ops output writes to:
- `~/.arkaos/design-ops/<slug>/` — generated artefacts (JSON, CSS, reports)
- `${VAULT_PATH}/Projects/Design Ops/<slug>.md` — human-readable summary (Obsidian)

## Boundaries

- Strategy and visual direction stay with **Valentina** (`/brand`).
- Iris escalates anything that requires brand-level taste calls.
- Design-ops never opens PRs or pushes code; it produces specs, tokens,
  audits. Implementation goes back to `/dev` via Paulo.

## Cross-references

- Pattern source: KB note `🧠 Knowledge Base/Frameworks/AIOX Squads` (2026-04-30 live)
- ADR: this skill is the v2.27.0 Conclave instantiation of the sub-squad pattern
- Parent: `/brand` (Valentina)
- Stack origin: v2.27.0 (PR5 of 6 from the 2026-05-13 Conclave roadmap)
