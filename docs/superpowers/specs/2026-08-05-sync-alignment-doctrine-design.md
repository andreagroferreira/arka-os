# Sync Alignment Doctrine — design spec

- **Date:** 2026-08-05 (revised 2026-08-06 after two Quality Gate rejections)
- **Branch:** `feat/sync-alignment-core`
- **Constitution:** `spec-driven` (MUST), `evidence-flow` (NON-NEGOTIABLE), `mandatory-qa`, `excellence-mandate`

## Problem

`/arka update` reports `78 unchanged` while nothing verifies that projects
are actually aligned. The operator's expectation — *"after an update the
project must be better: new things, new approaches, and it can even fix
things that were built wrong because ArkaOS did not have that feature
yet"* — is not met.

Measured on 78 real projects before any change:

| Finding | Evidence |
| --- | --- |
| Core content **is** aligned | 78/78 carry the current managed hash |
| The version stamp freezes | 38 projects stamped `4.23.0`, 13 `2.17.0` — all with current content |
| Ecosystem skills drift | 2 skills lost 2 canonical lines each, 2 more lost 1 |
| Phase 4 never ran in code | `engine.py` passed `skill_results=[]` |
| No migration mechanism | `manifest.py` only *lists* deprecated names; no repair code exists |
| The coverage gate measured nothing | `coverage.xml` predating the diff passed at 86.3% |

## Doctrine

Alignment is **not** "rewrite everything" — that deletes operator work.

> **ArkaOS owns what is inside its markers and rewrites it every sync. The
> project owns everything outside them and it is never touched. Where
> ownership is ambiguous, the tool proposes and the human applies.**

## Scope of THIS release

Deliberately reduced. The first attempt bundled a deterministic Phase 4
(`feature_merger.py` + `skill_syncer.py`) with everything below, and the
Quality Gate rejected it twice: both rounds found silent, unrecoverable
deletion of operator text in `~/.claude/skills/`, which is not a git
repository. The second round's finding was the sharper one — the
remediation fixed the marker *topology* it had a test for and declared the
contract closed, while block-content integrity was never instrumented.

Shipping the rest and holding the writer back is the honest split: the
value that is proven lands, and the component that writes into an
unversioned directory waits until its contract can be demonstrated rather
than asserted.

- **`restamped` and `drifted` in `content_merger`** — the stamp is a claim,
  so the body between the markers is hashed before anything is rewritten. A
  block the operator edited in place yields `drifted` and is left alone; a
  verified-current block with a stale stamp is `restamped`. Reported
  separately from `updated`, so a cosmetic restamp is never presented as a
  change.
- **Propose-only migration runner** — spec format, version gating, vendored
  tree skipping, both caps reported with honest labels, per-spec error
  isolation, and a wall-clock budget that abandons and records a scan whose
  regex backtracks pathologically (pattern shape is deliberately not
  judged — a shape heuristic refused ordinary patterns and missed the
  dangerous ones). No specs ship yet; the runner scans nothing until one
  exists.
- **Coverage gate honesty** — an artefact older than the changed source, or
  missing a changed module, fails the check. Module presence is matched on
  the parsed path, never on the filename stem.
- **Unorderable version baselines** — distinguished from "nothing is new".
- **Update-skill instructions** — the subagent may no longer delete an
  unmarked section, and needs a single well-formed marker pair to remove
  anything. Applied to both references of the bundle (`workflows.md` and
  `sync-engine.md`), in the `departments/` tree and its `plugins/` mirror.
- **Client identifiers** out of `.gitignore` / `.npmignore`.

## Deferred to a follow-up PR

Deterministic Phase 4 (`feature_merger.py`, `skill_syncer.py`). It does not
ship until, at minimum:

1. The managed block's **actual body** is hashed, not just the stored stamp
   compared to canonical, so operator drift inside a block is detected and
   proposed instead of overwritten.
2. `_find_block` contains foreign markers — per-feature-name validation
   cannot see an interleaved or nested layout belonging to another feature.
3. The legacy span is bounded at the first marker line, so `adopted` is
   reachable with a multi-feature registry.
4. All three Quality Gate reproductions ship as regression tests.

Until then Phase 4 remains the AI subagent, with the deletion instruction
removed.

## Non-goals

- Auto-applying migrations to project code.
- Rewriting core (npm-shipped) skills.
- Reconciling diverged legacy sections automatically.

## Acceptance criteria

1. `restamped` distinguished from `updated`; mutation-proven.
2. Migrations propose only; both caps reported only when something was
   actually discarded; a bad spec never aborts a run.
3. A stale or path-mismatched `coverage.xml` fails the coverage check.
4. An unorderable baseline reads as a first sync, never as "nothing new",
   and one malformed `added_in` cannot poison an orderable baseline.
5. No instruction anywhere permits deleting an unmarked section.
   Verify (`-E`, because BSD grep reads `\|` as a literal and would pass
   vacuously): `grep -rnE 'heading block|otherwise remove' departments/ plugins/`
   returns nothing.
6. No tracked file names a client.
7. Full suite green; `ruff` clean on every changed file; no function over
   30 lines that was not already over 30 on master.
