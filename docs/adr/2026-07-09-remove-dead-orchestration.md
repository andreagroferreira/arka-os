# ADR: Remove dead Python orchestration (WorkflowEngine, PhaseAnnouncer, SubagentDispatcher)

- **Date:** 2026-07-09
- **Status:** Accepted (closes the last open P1 of the E2E audit,
  2026-07-07; operator-delegated backlog decision, consolidation session
  2026-07-09)
- **Relates to:** ADR `2026-07-04-evidence-flow.md`, constitution rules
  `solid-clean-code` (no dead code) and `evidence-flow`.

## Context

The v4.3.6 end-to-end audit found two orchestration classes with zero
production callers, flagged P1 "wire or remove":

- `core/workflow/engine.py::WorkflowEngine` — a sequential phase
  executor for the YAML workflows. Consumers: unit/integration tests
  only.
- `core/runtime/subagent.py::SubagentDispatcher` (plus
  `SubagentResult`/`SubagentStatus`) — an in-Python dispatch ledger.
  Consumers: tests only.

A caller sweep on 2026-07-09 confirmed the finding and added a third:
`core/workflow/announcer.py::PhaseAnnouncer`, whose only documented
integration point was the WorkflowEngine `on_visibility` callback and
whose only consumer was its own test file.

Real orchestration in ArkaOS is the runtime: hooks (Synapse injection,
flow enforcement, gate checkpointing) + skills + the Task tool. The
audit's Agent SDK verdict stands: an SDK-based headless executor is the
right shape *if* headless execution (dashboard-triggered runs,
autonomous Dreaming) ever becomes a feature — these classes would not
be its foundation.

## Decision

**Remove the dead classes; keep the live contracts.**

Removed:
- `core/workflow/engine.py` (WorkflowEngine) and its package export.
- `core/workflow/announcer.py` (PhaseAnnouncer) + `test_announcer.py`.
- `SubagentDispatcher`, `SubagentResult`, `SubagentStatus` from
  `core/runtime/subagent.py` and their tests.
- Engine-execution tests re-scoped to structural/loader assertions
  (`test_workflow.py`, `tests/integration/test_e2e_workflow.py`).

Kept (load-bearing):
- `core/workflow/schema.py` + `loader.py` — the declarative contract
  for `departments/*/workflows/*.yaml`, validated across the whole
  catalog by `test_all_workflows.py`.
- `core/workflow/state.py` + `gate_checkpoint.py` — runtime state
  persistence (fed by the Stop hook since v4.1.0).
- `HandoffArtifact` in `core/runtime/subagent.py` — the measured
  handoff contract, consumed by `scripts/bench/harness.py` and built by
  `ContextCompactor`.

## Rationale

1. **Clean-code MUST**: dead code is a standing violation; git history
   preserves the implementation if it is ever wanted.
2. **One orchestration story**: two parallel execution models (narrated
   Python executor vs. evidence-flow runtime) is exactly the
   "narrated rigor" failure mode the 2026-07-04 evidence-flow ADR
   removed. The YAML tier/phase/gate contract survives intact — what
   goes is the unused Python simulation of it.
3. **Headless future ≠ these classes**: per the audit verdict, headless
   execution would be built on the Agent SDK against the same YAML
   contract, not on WorkflowEngine.

## Consequences

- `core.workflow` exports no executor; docs
  (`WORKFLOW-ENGINE.md`, `CORE-ENGINE.md`) now describe the runtime as
  the orchestrator of the declarative contract.
- ~725 lines of unused code and ~350 lines of tests-of-nothing removed.
- If headless execution lands on the roadmap, it starts from a fresh
  ADR + Agent SDK design, not from resurrecting the executor.
