---
name: arka-flow
description: >
  ArkaOS canonical evidence flow — the 4-gate (CONTEXT/PLAN/EXECUTE/REVIEW)
  default execution contract; gates pass on evidence read from disk
  (commands, exit codes, files), never on narration.
  TRIGGER: loads on EVERY non-trivial request inside an ArkaOS-managed
  context — any implementation/creation/change verb ("implementa",
  "cria", "corrige", "altera", "refactoriza", "implement", "build",
  "fix", "add", "refactor", "deploy"), and always when the hook injects
  [ARKA:WORKFLOW-REQUIRED]; load BEFORE the first Write/Edit/effect-Bash,
  not after.
  SKIP: single-file edits under 10 lines — emit "[arka:trivial] <reason>"
  and proceed; pure planning requests where arka-forge wins (this flow
  still wraps the eventual execution); spec authoring where arka-dev-spec
  wins at Gate 2.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# ArkaOS — Evidence Flow (4 gates)

> This flow runs on **every** non-trivial user request inside an
> ArkaOS-managed context. It replaced the 13-phase flow in v4.1.0
> (constitution rule `evidence-flow`, ADR
> `docs/adr/2026-07-04-evidence-flow.md`). A gate passes on **evidence**
> — command output, exit codes, files on disk — never on the model
> asserting that work happened.
>
> Bypass: single-file edit under 10 lines may emit
> `[arka:trivial] <reason>` as its first line and proceed directly.
> This bypass is first-class doctrine, not a loophole (constitution
> `autonomy.default_stance`): ArkaOS defaults to executing, and gates
> exist to catch risk, not to ritualize trivial work.

## The 4 gates (strict sequence)

Emit the gate marker on its own line when the gate STARTS. The Stop hook
persists every observed gate transition to the session's
`WorkflowSnapshot` (see Checkpointing below), so an interrupted session
resumes at the right gate.

### Gate 1 — CONTEXT `[arka:gate:1]`

- Route the request: emit `[arka:routing] <department-slug> -> <lead>`
  (mapping in `arka/SKILL.md`). Escalate to Tier 0 only when the request
  is strategic, cross-department, security-sensitive, or financial.
- Ground before asserting: Synapse has already injected KB matches
  (`[arka:kb-context:N]`) and, when a project graph exists, graph facts.
  Read them. Query `mcp__obsidian__search_notes` / the project graph for
  anything substantive they do not cover. Cite what you use with
  `[[wikilinks]]` or `file:line`; declare gaps explicitly.
- Read the live context: profile, CLAUDE.md, git branch, cwd tag,
  pattern cards (L7.5), agent experiences (L2.6).

### Gate 2 — PLAN `[arka:gate:2]`

- Produce a short plan: scope, files touched, how each change will be
  verified (the exact commands), what is explicitly out of scope.
- Complexity is scored by `core/forge/complexity.py`: LOW → a plan
  inline in the reply; MEDIUM/HIGH → persist the plan to
  `~/.arkaos/plans/` + Obsidian and consider `/arka-forge`.
- **Plan-judge (constitution `gate-judges`, MEDIUM/HIGH only):** BEFORE
  presenting the plan to the user, dispatch one judge via the Agent
  tool with `JUDGE_VERDICT_JSON_SCHEMA` from `core.governance.judge` as
  the structured-output schema, frontier model (constitution
  `quality_gate.model_policy`). The judge receives the original request
  + the plan and hunts adversarially for what is unfinished, default,
  or would be rejected by a top-tier lead — the same
  `arkaos-not-yes-man` standard applied to the AGENT's work. `REVISE`
  → fix the plan and re-judge (max 2 loops, then escalate the findings
  to the user). A non-empty `user_challenge` means the USER's request
  itself is technically wrong — present the challenge alongside the
  plan, never swallow it. Record every verdict:
  `arka-py -m core.evals.record_cli --kind judge`. LOW/trivial work
  skips the judge — gates catch risk, they do not ritualize.
- **Wait for EXPLICIT user approval. Silence is not approval.** This is
  the one human gate and it never disappears.
- Non-blocking unknowns do not stall the gate: proceed and state
  "Assuming: <choice>" so the operator can correct it cheaply. Ask early
  only for non-discoverable preferences/tradeoffs (2-4 options + a
  recommended default); discoverable facts are explored, never asked
  (constitution `autonomy.assuming_pattern`).

### Gate 3 — EXECUTE `[arka:gate:3]`

- Implement in atomic, independently verifiable steps (task tracker for
  3+ steps).
- Dispatch specialists via the Agent tool only when the work genuinely
  needs isolated context or parallelism (`subagent-discipline`).
  Announce every dispatch: `[arka:dispatch] <caller> -> <specialist>`.
- **Mechanical evidence, not narration:** before this gate closes, the
  relevant test suite MUST have been executed in this session and exit
  with 0. Report the real command and its result, e.g.:

  ```
  [arka:gate:3] evidence: pytest tests/python -q -> exit 0 (4521 passed)
  ```

  A failing suite loops back into implementation. Claiming success
  without a run on record is a constitution breach (`evidence-flow`).

### Gate 4 — REVIEW `[arka:gate:4]`

- Run the evidence checks that apply to the diff: linter, type-checker,
  coverage read from the report file, security grep, spell-check for
  copy. Reviewers (Quality Gate personas) interpret tool output; they do
  not replace it. APPROVED/REJECTED derives from evidence.
- **Output-judge (constitution `gate-judges`, MEDIUM/HIGH only):**
  BEFORE dispatching the Quality Gate personas, dispatch one judge
  (Agent tool, `JUDGE_VERDICT_JSON_SCHEMA`, frontier model) over the
  deliverable + diff + evidence report. `REVISE` loops the work back
  into Gate 3 (max 2); `PASS` and its findings become INPUT to the QG
  reviewers — the judge never replaces the personas or the evidence.
  Record the verdict: `arka-py -m core.evals.record_cli --kind judge`.
- **Excellence check (`excellence-mandate`, mandatory):** before closing,
  answer three questions with evidence, not narration:
  1. What is **unfinished** in this delivery (trimmed scope, TODO left
     behind, parity skipped)?
  2. What is **default** (template look, boilerplate copy, unstyled
     component, generic strategy)?
  3. What would a **top-tier lead reject** here? Name the benchmark
     (`reference_companies.application` — e.g. Linear/Stripe for
     frontend) and judge against it.
  A non-empty answer loops the work back into Gate 3 or is escalated to
  the operator as an explicit open-items decision. Shipping with a
  non-empty list and no operator decision is a constitution breach.
  Time and token cost are not acceptable answers to any of the three.
- Quality Gate REJECTED loops back at most twice; a third REJECTED
  escalates to the operator with the full verdict.
- Close with an honest summary: what changed, where, how it was
  verified (real commands + results), what remains open.

## Checkpointing and resume

`core/workflow/gate_checkpoint.py` (invoked by the Stop hook) scans the
turn for gate markers and persists them to BOTH stores:

- `~/.arkaos/workflow-state.json` (`core/workflow/state.py`)
- `~/.arkaos/sessions/<id>/workflow-state.json` (`SessionStore`, read by
  `core/memory/rehydrator.py` at SessionStart)

If a session dies mid-Gate-3 (rate limit, context exhaustion, crash),
the next SessionStart injects `[SESSION] Resuming at gate 3` with the
pending items. Do not restart from Gate 1 when a snapshot exists —
verify the snapshot against `git status` and continue.

## Visibility

Gate markers are the only mandatory ceremony. Inside a gate, work in
normal prose — no per-step phase tags, no verbatim echo of the request,
no six-reviewer role-play. One marker per gate transition.

## Hard no-go list

- No Write/Edit/effect-Bash before Gate 2 approval for the affected
  scope (`[arka:gate:1]`/`[arka:routing]` alone does not unlock writes).
- G2 approves the PLAN; irreversible or outward-facing side effects
  (send, publish, delete, merge, release, deploy) carry their own
  confirm-at-action-time gate — confirm at the moment of impact, even
  inside an approved plan. Vague consent is never blanket permission
  (constitution `autonomy.levels`).
- No closing Gate 3 without a real test run on record (command + exit
  code in the transcript).
- No pushing to master without Gate 4 evidence on every changed item.
- No `[arka:trivial]` when the change spans more than one file or
  exceeds 10 lines.
- No skipping Gate 2 approval. The user is the gate, not a hint.

## Related skills

- `/arka-forge` — complexity-aware planning for MEDIUM/HIGH Gate 2.
- `arka-dev-spec` (`/dev spec`) — spec gate when Gate 2 scope needs a full spec.
- `/arka-quality` — Gate 4 orchestration.
- `/arka-checkpoint` — user-in-the-loop fragmentation for >30s dispatches.

## Non-negotiable

The UserPromptSubmit hook classifies every turn. When it injects
`[ARKA:WORKFLOW-REQUIRED]`, this flow is the contract. The SessionStart
hook embeds it as `systemMessage`. Constitution rule `evidence-flow`
codifies it. Legacy `[arka:phase:N]` markers remain accepted by the
enforcer during the v4.1 deprecation window but new work emits
`[arka:gate:N]`.
