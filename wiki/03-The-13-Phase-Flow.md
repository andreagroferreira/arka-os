# 03 · The Evidence Flow (4 Gates)

← [Core Concepts](02-Core-Concepts.md) · [Home](Home.md) · Next: [Departments →](04-Departments/)

Every non-trivial request inside ArkaOS runs the same canonical sequence. There
is no "simple mode" and no "skip it this time". The single exception is a
trivial one-file edit under 10 lines, which may emit `[arka:trivial] <reason>`
and bypass. Everything else runs the 4 gates.

This is constitutional (`evidence-flow`, NON-NEGOTIABLE). The full spec lives
at `arka/skills/flow/SKILL.md`.

> **History:** the evidence flow replaced the 13-phase flow in v4.1.0
> (ADR `docs/adr/2026-07-04-evidence-flow.md`). A July 2026 audit showed the
> 13 phases burned ~110-150k tokens per feature while most of the rigor was
> narrated, not enforced. The legacy `[arka:phase:N]` markers remain accepted
> during a deprecation window (removal target v4.3.0).

---

## Why evidence, not ceremony

A gate passes on **evidence read from disk** — command output, exit codes,
report files — never on the model asserting that work happened. The flow keeps
the three things that demonstrably protect quality (grounded context, explicit
human approval, a real test run) and drops the narrated ceremony that only
consumed tokens.

At each gate start, ArkaOS emits `[arka:gate:N]` so you can see exactly where
it is — and so the Stop hook can checkpoint progress for resume.

## The 4 gates

| # | Gate | Marker | Passes on |
|---|---|---|---|
| 1 | **CONTEXT** | `[arka:gate:1]` | `[arka:routing] <dept> -> <lead>` + KB/graph grounding with citations (`[[wikilinks]]` / `file:line`) or an explicit gap declaration. |
| 2 | **PLAN** | `[arka:gate:2]` | A short plan (scope, files touched, verification commands) + **explicit user approval**. Silence is not approval. |
| 3 | **EXECUTE** | `[arka:gate:3]` | Atomic implementation steps. Closes ONLY with a real test run on record: `[arka:gate:3] evidence: <command> -> exit 0 (<summary>)`. A failing suite loops back. |
| 4 | **REVIEW** | `[arka:gate:4]` | Executable checks for the diff — linter, type-checker, coverage read from the report, security grep, spell-check for copy — plus an honest closing summary. |

Specialist dispatches inside Gate 3 are still announced with
`[arka:dispatch] <caller> -> <specialist>` (constitution rule
`dispatch-must-be-announced`).

## Checkpointing and resume

The Stop hook runs `core/workflow/gate_checkpoint.py` after every assistant
turn. Each observed gate transition is persisted to two stores:

- `~/.arkaos/workflow-state.json` (global, `core/workflow/state.py`)
- `~/.arkaos/sessions/<id>/workflow-state.json` (per-session `SessionStore`,
  read by `core/memory/rehydrator.py` at SessionStart)

If a session dies mid-Gate-3 — provider rate limit, context exhaustion, crash —
the next SessionStart injects the snapshot (current gate, pending items) and
work continues from where it stopped instead of restarting the flow.

## Enforcement

- The UserPromptSubmit classifier marks creation/implementation turns as
  flow-required; with `hooks.hardEnforcement=true`, PreToolUse blocks effect
  tools (Write/Edit/Task/Skill/effect-Bash) until a flow marker
  (`[arka:routing]`, `[arka:gate:N]`, `[arka:trivial]`, or legacy
  `[arka:phase:N]`) appears in recent assistant messages.
- SessionStart injects the `[ARKA:EVIDENCE-FLOW]` contract as a systemMessage.
- The Stop hook checks the closing marker (`[arka:gate:4]` or
  `[arka:trivial]`) and records compliance telemetry.

**Hard no-go list:** no writes before Gate 2 approval for the affected scope;
no closing Gate 3 without a test run on record; no pushing to master without
Gate 4 evidence; no `[arka:trivial]` beyond one file / 10 lines; no skipping
Gate 2 approval.

---

← [Core Concepts](02-Core-Concepts.md) · [Home](Home.md) · Next: [Departments →](04-Departments/)
