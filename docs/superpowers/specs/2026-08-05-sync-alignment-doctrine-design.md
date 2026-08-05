# Sync Alignment Doctrine — design spec

- **Date:** 2026-08-05
- **Branch:** `feat/sync-alignment-doctrine`
- **Constitution:** `spec-driven` (MUST), `evidence-flow` (NON-NEGOTIABLE), `excellence-mandate`
- **Approved at G2 by the operator** ("Sim força", 4 PRs, order B → A → C → D)

## Problem

`/arka update` reports `78 unchanged` while ecosystem skills silently
diverge. The operator's expectation — *"after an update the project must be
better: new things, new approaches, and it can even fix things that were
built wrong because ArkaOS did not have that feature yet"* — is not met on
three surfaces.

Measured evidence, this branch's investigation:

| Finding | Evidence |
| --- | --- |
| Core content **is** aligned | 78/78 projects carry managed hash `d83f5e17524e` |
| Version stamp lies | 38 projects stamped `4.23.0`, 13 `2.17.0` — all with current content |
| Ecosystem skills drift | 2 skills lost 2 canonical lines each, 2 more lost 1 |
| Phase 4 never ran in code | `engine.py` passed `skill_results=[]`; Phase 4 was an AI subagent told only to "inject if missing" |
| No migration mechanism | `manifest.py::_find_deprecated_features` only *lists* names; no removal or repair code exists |

## Doctrine

Alignment is **not** "rewrite everything". Rewriting everything deletes
operator work — one ecosystem carries its real spec list, another a tiers
table adapted to multi-module impact, a third a hardened
`## Quality Gate (NON-NEGOTIABLE)`.

The rule, already proven by `content_merger.py` on `.claude/CLAUDE.md`:

> **ArkaOS owns what is inside its markers and rewrites it on every sync.
> The project owns everything outside them and it is never touched.
> Where ownership is ambiguous, the tool proposes and the human applies.**

## Scope

### PR-B — honest version stamp

`merge_managed_content` gains a `restamped` status: content hash matches but
the stamp is stale → rewrite the stamp. Surfaced separately from `updated`
so a real content change is never confused with a cosmetic one.

### PR-A — deterministic Phase 4

- `feature_merger.py` — per-feature managed blocks (`version=` + `hash=`),
  rewritten from the canonical registry every run.
- `skill_syncer.py` — applies it to **user-owned skills only**: installed
  `arka-*` whose slug has no `SKILL.md` in the core repo (10 of 333). Core
  skills ship from npm and are replaced by `npx arkaos update`; rewriting
  them here would fight the installer. **Fail-closed**: no readable core
  repo → sync nothing, never "everything looks user-owned".
- Legacy sections (no markers) are adopted **only when byte-identical** to
  canonical. Divergence is written to a `.arkaos-adopt.md` proposal and the
  installed file is left untouched.
- Deprecation removes a marked block; a diverged legacy section becomes
  `pending_removal`, never a silent delete.

### PR-C — propose-only migrations

`core/sync/migrations/*.yaml` → `MigrationSpec(name, added_in, description,
detect, paths, replace, guidance)`. Runs only for versions newer than the
last sync; a first sync runs none. Scans skip vendored trees, cap at 2000
files/project and 20 hits/migration/project, and **log every cap** rather
than truncating silently. Output is one reviewable file under
`~/.arkaos/migration-proposals/<version>.md`. **Never writes to a project.**

### PR-D — a report that communicates value

Skills line, restamp counts, adoption-pending counts, migration hits.

## Non-goals

- Auto-applying migrations to project code.
- Rewriting core (npm-shipped) skills.
- Reconciling the 20 diverged legacy sections automatically — that is the
  operator's judgement call, surfaced by proposals.

## Acceptance criteria

1. `restamped` distinguished from `updated`; mutation-proven test.
2. Stale feature block rewritten from canonical; project text preserved.
3. Diverged legacy section never overwritten; mutation-proven test.
4. Discovery fail-closed without a core repo.
5. Whole pipeline idempotent: second run reports zero `updated`.
6. Migrations propose only; caps reported.
7. Full suite green.
