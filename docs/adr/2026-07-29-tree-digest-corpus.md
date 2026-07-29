# ADR: The tree-digest primitive is deferred to a dedicated PR; its acceptance spec is the QG route corpus

- **Date:** 2026-07-29
- **Status:** accepted
- **Decision maker:** operator (option B of the round-10 escalation)
- **Context PR:** PR-B2 (`feat/qg-integrity-digests`)

## Decision

PR-B2 ships the dict-digest primitives (`evidence_digest`,
`verdict_digest`) and the optional QGVerdict/JudgeVerdict digest
fields. A working-tree digest does NOT ship: `QGVerdict.tree_digest`
is RESERVED and enforced empty by the validator until a dedicated PR
produces the primitive and survives its own Quality Gate.

## Why

Inside PR-B2, three designs of a `tree_digest` were driven through
ten Quality Gate rounds. The aggregate (Marta) and the technical
reviewer (Francisca) kept reproducing wrong-digest routes — states
where the primitive returned a non-empty digest while blind to a
real difference between trees; the copy reviewer's rounds closed the
claim and provenance defects in how they were recorded. Rather than
ship a primitive whose defect class kept resurfacing, the operator
cut it.

## The route corpus (acceptance spec for the dedicated PR)

Each route below was reproduced at the gate — by the technical
reviewer or the aggregate — with a working script before being
accepted. A candidate tree-digest implementation must hold ALL of
these as property tests:

1. **Porcelain-parse blindness** (design 1): untracked-directory
   content and C-quoted (non-ASCII/space) paths never hashed; content
   changes invisible.
2. **Rename-origin loss** (design 1→2): two same-HEAD trees renaming
   different identical-content files onto one destination digested
   equal once the origin left the material (the bytes fed to the
   digest).
3. **Work-tree-column renames + parser cascade + CR corruption**
   (design 2): ` R`-column renames fabricated entries; a mis-parsed
   origin swallowed the next real entry; text-mode universal newlines
   rewrote `\r` in paths.
4. **Subdirectory resolution** (design 2): porcelain paths are
   root-relative; joining them to a subdirectory `project_dir`
   resolved every entry to a nonexistent file.
5. **Root-name whitespace + ambient environment** (design 2):
   `.strip()` ate a root name's trailing whitespace; ambient
   `GIT_DIR`/`GIT_CONFIG_*`/`core.excludesFile` overrode the argument
   or forged exclusions (git exports `GIT_DIR` to hooks).
6. **Colon-split alternates / racy stat trust / tracked-but-ignored
   blindness** (design 3): `GIT_ALTERNATE_OBJECT_DIRECTORIES` is a
   colon-split list; a seeded scratch index imported the real index's
   stat cache (same-size same-mtime changes passed unread); an
   unseeded one skipped tracked-but-ignored files — including
   `.claude/rules/*.md` and the QG's own screenshot evidence.

Additional requirements from the final aggregate (round 10): a
production design needs seeding PLUS an explicit defeat of the stat
cache, and one test that holds both properties simultaneously; plus
the standing requirements carried forward — a caller-side deadline
(git-call worst case exceeds the per-turn hook budget), a golden
material-layout vector (digest values are not comparable across
material shapes), and a surrogate-bearing path decode test that runs
only on Linux (`skipif` elsewhere).

## Primary artifacts

The verbatim reviewer/aggregate artifacts (with reproduction scripts
referenced in their text) live in the Quality Gate ledger on the
originating operator's machine, under
`~/.arkaos/quality-gate/49e47eaa-8ae5-4a4c-8d8d-14834e4cad77/`,
artifacts `francisca-tech-7..15` and `marta-cqo-3..10` (earlier
sequence numbers in that session belong to a different PR; ids
repeat across sessions, so the session id above is load-bearing).
The eval labels are in `~/.arkaos/telemetry/qg-verdicts.jsonl`. This
ADR is the durable summary; the ledger is the full record.
