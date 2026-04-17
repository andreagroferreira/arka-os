---
id: ADR-2026-04-17-binding-flow-enforcement
title: Binding Enforcement of the Mandatory 13-Phase Flow
status: accepted
date: 2026-04-17
deciders: Andre Groferreira (owner), Marco (CTO), Paulo (Dev Lead)
supersedes: null
related:
  - config/constitution.yaml#mandatory-flow
  - arka/skills/flow/SKILL.md
  - docs/adr/2026-04-11-multi-runtime-agnostic.md
---

# ADR — Binding Enforcement of the Mandatory 13-Phase Flow

## Status

Accepted — 2026-04-17

## Context

ArkaOS defines a 13-phase canonical workflow as a NON-NEGOTIABLE constitution
rule (`mandatory-flow`). Until this ADR, enforcement was **100% advisory**:

- `SessionStart` hook injects `[ARKA:MANDATORY-FLOW]` via `systemMessage`
- `UserPromptSubmit` hook injects `[ARKA:WORKFLOW-REQUIRED]` via `additionalContext`
- `PostToolUse` hook records violations post-hoc via `core/workflow/enforcer.py`
- No `PreToolUse` hook exists → `Write`, `Edit`, `MultiEdit`, `Bash` tool calls
  always pass through
- No `Stop` hook exists → final response is never validated

Observed failure: in multiple client projects (Rockport, and per-owner
auto-memory others), the Claude Code runtime skipped the flow repeatedly —
wrote amateur CRUD with `.env` hardcoded values, skipped Phase 7 (six
parallel reviewers), delivered, was corrected, then skipped the flow again.
Owner is furious and the cycle is reproducible.

The runtime primitive required for binding enforcement **exists**: the repo's
own `.claude/rules/bash-hooks.md` states `exit code 2 = block action`, and
`config/hooks/post-tool-use.sh` already uses `core/workflow/enforcer.py` as
a post-hoc enforcer. The primitive was simply never wired into the gates
where it matters — **before** a write-mutation tool executes.

## Decision drivers

1. **Stop the cycle** — advisory is proven insufficient; enforcement must
   structurally block mutation tools when the flow was skipped.
2. **Minimize false positives** — blocking `Read`/`Grep`/`Bash` would
   deadlock the runtime (cannot read `CLAUDE.md`, cannot run `git status`).
3. **Multi-runtime reality (ADR-001)** — `PreToolUse` with `exit 2` is
   Claude Code only. Codex, Gemini and Cursor expose no equivalent
   primitive (verified against Claude Code hooks docs, 2026-04-17).
4. **Owner confidence (30K users)** — any regression in `npx arkaos update`
   or the `/arka` skill collapses trust. Rollout must be gated and reversible.
5. **Escape hatch** — legitimate urgencies exist. `[arka:trivial]` must be
   a declarative, auditable bypass.

## Alternatives considered

### Alt A — Pure bash PreToolUse + Stop + classifier keyword + /tmp state
- Pros: zero new deps, deploys via existing installer
- Cons: bash has no pytest; `/tmp` state introduces race conditions in
  parallel sessions; classifier regex fragile; maintenance fragmented
- **Rejected**: frail, immediate tech debt

### Alt B — Single Python hook (PreToolUse) doing everything
- Pros: one entry point, pytest coverage, structured logging, Pydantic-validated state
- Cons: Python cold-start 150-300ms per `Write`/`Edit` tool call; Stop hook still needed
- **Partially adopted**: the enforcement logic **is** Python, living in
  `core/workflow/flow_enforcer.py`. Bash hook is only a thin wrapper.

### Alt C — Agent-level only (system prompt + prefill)
- Pros: zero hooks, universal across runtimes
- Cons: enforcement is probabilistic (already proven insufficient — this
  is effectively what we have today)
- **Rejected as sole solution**, retained as Layer 1

### Alt D — Full Workflow State Machine (semantic phase tracking)
- Pros: semantically correct; `can_write?` derived from `phase_current ∈ {10, 11}`
- Cons: 8-12 dev-days; parsing transcript to infer current phase is non-trivial;
  false-positive risk (blocking legitimate work) is the worst UX
- **Rejected for now**: correct long-term but too slow for current urgency

### Alt E — HYBRID (adopted)
Layer 1 (universal) + Layer 2 (binding, Claude Code only).

## Decision

**Adopt Alternative E.** Specifically:

### Layer 1 — Universal (all runtimes)
Keep existing `SessionStart` systemMessage + `UserPromptSubmit`
`additionalContext` injections unchanged. They provide a universal
advisory baseline for Codex/Gemini/Cursor.

### Layer 2 — Binding (Claude Code only)

**New hook `config/hooks/pre-tool-use.sh`** (thin bash wrapper →
`core/workflow/flow_enforcer.py`):

| Aspect | Value |
|---|---|
| Intercepted tools | `Write`, `Edit`, `MultiEdit` **only** |
| Never-blocked tools | `Read`, `Grep`, `Glob`, `ToolSearch`, `TaskCreate`, `Agent`, `WebFetch`, `WebSearch`, `Bash` |
| Permission signal | Last 3 assistant messages in `transcript_path` contain `[arka:routing]` OR `[arka:trivial]` OR `[arka:phase:` |
| Fail mode | Exit 2 with stderr message (or `hookSpecificOutput.permissionDecision: "deny"`) |
| State | **Stateless** — transcript re-parse each invocation, no `/tmp` state file |
| Cache | `/tmp/arka-phase-cache/<session_id>` TTL 2s; accelerates allow decisions only — never the sole basis for a deny |
| Escape hatch | `[arka:trivial] <reason>` in the preceding assistant message |
| Kill switch | `ARKA_BYPASS_FLOW=1` env var (used by installer/`/arka update`); every bypass logged to `~/.arkaos/audit/bypass.log` |
| Feature flag | `hooks.hardEnforcement` in `~/.arkaos/config.json`, default `false` in v2.20.0-beta, promoted to `true` in v2.21.0 after ≥ 2 weeks clean telemetry |

**New hook `config/hooks/stop.sh`** (warn mode):
- If the classifier matched creation/implementation intent during the
  session, validate the final assistant message contains `[arka:phase:13]`
  or `[arka:trivial]`.
- **Warn mode**: log to `~/.arkaos/telemetry/enforcement.jsonl`, always
  exit 0. Promoted to `strict` only after 2 weeks of clean telemetry.

**Shared lib `config/hooks/_lib/workflow-classifier.sh`:**
- Extracts current inline classifier (user-prompt-submit.sh lines 284-328)
- Reused by `user-prompt-submit.sh`, `pre-tool-use.sh`, `stop.sh`

**Spoofing defense:**
- When classifier matches, `user-prompt-submit.sh` writes
  `/tmp/arkaos-wf-required/<session_id>` with a timestamp.
- `pre-tool-use.sh` reads that file (not just assistant text) to know if
  flow is required for that session.
- `PostToolUse` cross-checks: if `[arka:routing] dev -> Paulo` was emitted,
  the subsequent `Task` dispatch must have `subagent_type` compatible with
  the announced `<lead>`. Divergence = violation logged.

### Windows parity
`pre-tool-use.ps1` + `stop.ps1` ship in the same commit. No runtime is left
with partial enforcement.

## Rollout

| Milestone | Action | Gate |
|---|---|---|
| v2.20.0-beta.1 | Release `arkaos@beta` with flag `false` default | Canary self-test in installer passes |
| T+0 → T+72h | Owner opts in via `/arka config set hooks.hardEnforcement true` in arka-os (dogfooding) | < 5% false positives in 72h telemetry |
| v2.20.0 | Release `arkaos@latest` with flag `false` default, docs explaining opt-in | QG approved |
| T+2 weeks | If telemetry stays clean, flip default to `true` in v2.21.0 | Owner explicit go |

## Consequences

### Positive
- Advisory → binding for the most destructive tool category (code mutations)
- Stateless parse eliminates the race-condition class
- Python-native enforcement (`flow_enforcer.py`) is pytest-covered and
  respects anti-pattern `duplicated-security-logic` (bash is only a wrapper)
- Feature flag + canary self-test + rollback command keep 30K-user risk
  bounded
- `[arka:trivial]` escape hatch preserves agility for legitimate single-file
  edits

### Negative
- Enforcement is Claude Code only; other runtimes remain advisory-only
  (documented limitation of the primitive)
- Classifier is regex-based — semantic drift over time will require
  classifier tuning
- Tag-forging defense is partial (PostToolUse cross-check is best-effort,
  not semantic proof of phase execution)

### Neutral
- Opt-in default for v2.20.0 means the binding is not "on" for all users
  immediately — intentional trade-off for safety

## Out of scope

- Full 13-phase semantic state machine (Alt D) — revisit in v3
- Perfect anti-spoof verification (proving each phase actually executed)
- Binding enforcement in Codex/Gemini/Cursor — blocked on upstream primitive
  availability

## References

- `arka/skills/flow/SKILL.md` — full 13-phase specification
- `config/constitution.yaml` — `mandatory-flow` rule
- `core/workflow/enforcer.py` — existing post-hoc enforcer (reused pattern)
- Claude Code hooks docs (confirmed 2026-04-17): `PreToolUse` exit 2 blocks,
  `transcript_path` JSONL format, `session_id` via stdin
- Obsidian: `anti-pattern-duplicated-security-logic.md`,
  `anti-pattern-shipping-acknowledged-no-ops.md`
- Plan: `~/.arkaos/plans/2026-04-17-binding-flow-enforcement.md`
