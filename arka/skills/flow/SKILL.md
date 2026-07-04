---
name: arka-flow
description: >
  ArkaOS canonical evidence flow. 4 gates. This is the default execution
  contract for every user request inside an ArkaOS-managed context.
  Gates pass on evidence read from disk, not on narration.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
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
- **Wait for EXPLICIT user approval. Silence is not approval.** This is
  the one human gate and it never disappears.

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
- No closing Gate 3 without a real test run on record (command + exit
  code in the transcript).
- No pushing to master without Gate 4 evidence on every changed item.
- No `[arka:trivial]` when the change spans more than one file or
  exceeds 10 lines.
- No skipping Gate 2 approval. The user is the gate, not a hint.

## Related skills

- `/arka-forge` — complexity-aware planning for MEDIUM/HIGH Gate 2.
- `/arka-spec` — spec gate when Gate 2 scope needs a full spec.
- `/arka-quality` — Gate 4 orchestration.
- `/arka-checkpoint` — user-in-the-loop fragmentation for >30s dispatches.

## Non-negotiable

The UserPromptSubmit hook classifies every turn. When it injects
`[ARKA:WORKFLOW-REQUIRED]`, this flow is the contract. The SessionStart
hook embeds it as `systemMessage`. Constitution rule `evidence-flow`
codifies it. Legacy `[arka:phase:N]` markers remain accepted by the
enforcer during the v4.1 deprecation window but new work emits
`[arka:gate:N]`.
