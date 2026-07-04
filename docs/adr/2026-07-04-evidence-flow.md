# ADR: Evidence Flow replaces the 13-phase mandatory flow

- **Date:** 2026-07-04
- **Status:** Accepted (operator decision, plan "ArkaOS v4.1 — De Teatro a Entrega")
- **Supersedes:** constitution rule `mandatory-flow`; parts of
  `docs/adr/2026-04-17-binding-flow-enforcement.md` (marker taxonomy).

## Context

A July 2026 ground-truth audit found the 13-phase flow was the single
biggest token amplifier (~110-150k tokens and 15+ opus calls for a
5-todo feature) while its rigor was almost entirely narrated, not
enforced: the "six parallel reviewers" had no orchestrator, the
per-todo QA/Security/Quality-Gate chain validated self-reported
booleans, `core/workflow/state.py` had no callers (no structured
checkpoint, no resume after a rate-limit interruption), and the
enforcer only checked that *a* marker string existed. The system spent
tokens narrating ceremony instead of producing verified deliverables.

## Decision

Replace the 13 phases with 4 gates that pass on **evidence read from
disk** — command output, exit codes, report files — never on the model
asserting that work happened:

| Gate | Marker | Passes on |
|---|---|---|
| G1 CONTEXT | `[arka:gate:1]` | `[arka:routing]` + KB/graph grounding with citations |
| G2 PLAN | `[arka:gate:2]` | short plan + EXPLICIT user approval |
| G3 EXECUTE | `[arka:gate:3]` | real test run on record (command + exit 0) |
| G4 REVIEW | `[arka:gate:4]` | executable checks (lint/type/coverage/security/spell) |

Supporting changes:

- Constitution: `mandatory-flow` → `evidence-flow` (level unchanged:
  NON-NEGOTIABLE).
- `core/workflow/gate_checkpoint.py` (Stop hook) persists every gate
  transition to `~/.arkaos/workflow-state.json` AND the per-session
  `SessionStore` snapshot, so `core/memory/rehydrator.py` resumes an
  interrupted session at the correct gate.
- Per-turn injections shrink: `_WORKFLOW_DIRECTIVE` ~450 → ~80 tokens;
  SessionStart banner compacted.
- `[arka:phase:N]` markers stay accepted by `flow_enforcer.py` during
  the v4.1 deprecation window; removal target v4.3.0.

## Consequences

- Expected ≥60% token reduction per feature (verified by the benchmark
  harness before release).
- The human approval gate (G2) is preserved unchanged.
- Mechanical evidence for G3/G4 is deepened in the v4.1 series
  (evidence engine PR: lint/type/coverage/security executables); until
  then the contract requires the test-run evidence line in the
  transcript.
- Six-reviewer role-play and per-todo triple-persistence are removed
  from the contract entirely.
