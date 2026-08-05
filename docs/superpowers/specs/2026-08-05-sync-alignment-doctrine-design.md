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
- Legacy sections (no markers) are adopted **only when identical once
  surrounding whitespace is trimmed** to canonical, and adoption preserves
  the project's own blank lines. Divergence is written to a `.arkaos-adopt.md` proposal and the
  installed file is left untouched.
- Deprecation removes a marked block; a diverged legacy section becomes
  `pending_removal`, never a silent delete.

### PR-C — propose-only migrations

`core/sync/migrations/*.yaml` (fallback
`~/.arkaos/config/sync/migrations/*.yaml`) → `MigrationSpec(name, added_in,
description, detect, paths, replace, guidance)`. **No specs ship in this
release**, so the runner scans nothing until one exists. When they do: only
versions newer than the last sync run; a first sync runs none; scans skip
vendored trees, cap at 2000 files per project per migration and 20 hits per
migration, and **both caps are reported** rather than truncating silently.
Output is one reviewable file under
`~/.arkaos/migration-proposals/<version>.md`. **Never writes to a project.**
A malformed spec or a bad regex is recorded against that spec; it never
aborts a sync that has already written to disk.

### PR-D — a report that names what changed

The skills line reports updates, restamps and unchanged counts separately;
diverged sections and broken markers are called out with their proposal
path; migration hits are shown as proposals, never as applied changes; and
every scan cap is printed rather than silently truncating.

## Non-goals

- Auto-applying migrations to project code.
- Rewriting core (npm-shipped) skills.
- Reconciling the diverged legacy sections automatically — that is the
  operator's judgement call, surfaced by proposals. Measured on the install
  this was developed against: 13 sections across 6 skills (counted by
  running `merge_feature` over every user-owned skill and tallying
  `pending_adoption` / `pending_removal`).

## Acceptance criteria

1. `restamped` distinguished from `updated`; mutation-proven test.
2. Stale feature block rewritten from canonical; project text preserved.
3. Diverged legacy section never overwritten; mutation-proven test.
4. Discovery fail-closed without a core repo.
5. Whole pipeline idempotent: second run reports zero `updated`.
6. Migrations propose only; **both** caps reported; a bad spec never aborts
   the run.
7. Malformed markers (orphan, duplicate, inverted) never splice — the file
   is left byte-identical and reported; regression-tested.
8. A stale or incomplete `coverage.xml` fails the coverage check instead of
   vouching for unmeasured code.
9. Full suite green, `ruff` clean on every file the PR touches.
