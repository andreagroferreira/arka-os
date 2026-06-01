# 03 · The 13-Phase Flow

← [Core Concepts](02-Core-Concepts.md) · [Home](Home.md) · Next: [Departments →](04-Departments/)

Every non-trivial request inside ArkaOS runs the same canonical sequence. There
is no "simple mode" and no "skip it this time". The single exception is a
trivial one-file edit under 10 lines, which may emit `[arka:trivial] <reason>`
and bypass. Everything else runs all 13 phases.

This is constitutional (`mandatory-flow`, NON-NEGOTIABLE). The full spec lives
at `arka/skills/flow/SKILL.md`.

---

## Why a fixed flow

A single AI assistant improvises: it sometimes plans, sometimes tests,
sometimes documents. ArkaOS makes the right behavior *structural* instead of
optional. The flow guarantees that every substantive piece of work is routed,
researched, planned, approved, executed, tested, security-checked,
quality-gated, and documented — in that order, every time.

Before each step, ArkaOS emits `[arka:phase:N] <label>` so you can see exactly
where it is.

## The 13 phases

| # | Phase | What happens |
|---|---|---|
| 1 | **Input** | Your request is captured verbatim — no paraphrasing yet. |
| 2 | **Get context** | Reads profile, working directory, `CLAUDE.md`, git branch/commits, ecosystem tags, recent session digests. |
| 3 | **Decide route** | Emits `[arka:routing] <dept> -> <lead>`. The department and lead are now committed. |
| 4 | **Call hierarchy** | Escalates to the C-Suite (Tier 0) when the request is strategic, cross-department, security-sensitive, or financial. |
| 5 | **Research** | Queries the knowledge base (Obsidian + vector DB), prior session digests, Forge plans, and the Pattern Library. Cites sources or declares a gap. |
| 6 | **Call team** | The lead dispatches specialists via the Agent tool, in parallel when work is independent. |
| 7 | **Plan** | Six parallel reviewer lenses: positive analyst, devil's advocate, Q&A, KB research, best-solution validator, pessimist. |
| 8 | **Present plan** | The plan is saved (Obsidian + vector DB + `~/.arkaos/plans/`) and shown to you. |
| 9 | **Wait for approval** | Explicit user "go". Silence is not approval. |
| 10 | **TODO list** | Atomic, ordered, independently verifiable tasks. |
| 11 | **Per-todo loop** | For each task: team call → complete → QA (all tests, E2E, Playwright) → Security → Quality Gate → Document. |
| 12 | **Loop** | Repeat phase 11 until the TODO list is exhausted. |
| 13 | **Summary** | What was done, where, how to verify, and what remains open. |

## The transparency tags

ArkaOS narrates itself with a small tag vocabulary. You'll see these in real
responses:

| Tag | Meaning |
|---|---|
| `[arka:routing] dev -> Paulo` | Phase 3 — the request was routed here |
| `[arka:phase:N] <label>` | The flow is entering phase N |
| `[arka:trivial] <reason>` | The trivial bypass was taken (1-file, <10 lines) |
| `[arka:meta] kb=N research=X persona=Y gap=Z critic=W` | End-of-turn transparency: how many KB notes were read, which research tools ran, who drove the answer, and the self-critic verdict |

## The per-todo loop (phase 11) in detail

This is where work actually ships. Each TODO runs the full gauntlet:

```
team call    -> the right specialists implement the task
complete     -> the change is made
QA           -> the ENTIRE test suite runs (never a subset), plus E2E/Playwright
Security     -> OWASP-style review where relevant
Quality Gate -> Marta + Eduardo + Francisca (Opus) — APPROVED or REJECTED
Document     -> the work is written back to Obsidian + the vector DB
```

If any gate fails, the loop does not advance. A REJECTED Quality Gate sends the
task back, not forward.

## Enforcement

The flow is enforced by hooks, not goodwill:

- The **SessionStart** hook injects `[ARKA:MANDATORY-FLOW]`.
- The **UserPromptSubmit** hook adds `[ARKA:WORKFLOW-REQUIRED]` on
  creation/implementation verbs.
- A **PreToolUse** gate blocks `Write`/`Edit`/`MultiEdit`/`Task` when no
  `[arka:routing]` or `[arka:trivial]` marker is present (when hard enforcement
  is on). Bypass once with `ARKA_BYPASS_FLOW=1`.

Skipping the flow violates `mandatory-flow`, `squad-routing`, `spec-driven`,
`mandatory-qa`, `sequential-validation`, `full-visibility`, and
`arka-supremacy`.

---

Next: [Departments](04-Departments/) — the teams that execute inside this flow.
Related: [Quality Gate](10-Quality-Gate.md), the gate that runs in phase 11.
