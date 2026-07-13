---
id: ADR-2026-05-28-specialist-dispatch-subagent-blindspot
title: Specialist-Dispatch Enforcement is a Negative Gate Only
status: accepted
date: 2026-05-28
deciders: Andre Groferreira (owner), Marta (CQO), Francisca (Tech Director)
supersedes: null
related:
  - config/constitution.yaml#dispatch-must-be-announced
  - core/workflow/specialist_enforcer.py
  - arka/skills/flow/SKILL.md
  - docs/adr/2026-04-17-binding-flow-enforcement.md
---

# ADR — Specialist-Dispatch Enforcement is a Negative Gate Only

## Status

Accepted — 2026-05-28

## Context

PR1 of the Squad Intelligence Upgrade introduces `core.workflow.specialist_enforcer`, a PreToolUse gate that blocks Tier-1 squad leads (Paulo, Ines, Daniel, …) from writing to specialist-owned files (`*.vue`, `**/app/Services/**`, `**/.env*`, …) when they have not first dispatched the matching specialist via the `Agent` tool.

The enforcer reads the session transcript at `transcript_path` (passed by Claude Code on every PreToolUse invocation) and resolves the "current persona" from the most recent `[arka:routing] <dept> -> <name>` or `[arka:dispatch] <from> -> <to>` marker.

The architectural reality, exposed by Francisca's QG review:

1. **Claude Code subagents run with isolated transcripts.** When Paulo dispatches `Task(frontend-dev)`, the `frontend-dev` subagent receives only the prompt the orchestrator sent — it does **not** see Paulo's main-thread transcript, including any `[arka:routing]` or `[arka:dispatch]` markers Paulo emitted.
2. **PreToolUse fires inside the subagent** when the subagent calls `Write`/`Edit`. The `transcript_path` provided to the hook is the subagent's, not the parent's.
3. Consequence: when `frontend-dev` writes `App.vue`, the enforcer's `_resolve_persona` returns `None` (no marker in the subagent transcript) and the gate returns `Decision(allow=True, reason="no-routing-tag")`. The write proceeds — but **not** via the positive `owner-match:frontend-dev` path. The specialist's identity is never proven; the gate simply fails open.

This means the enforcer is a **negative gate** on the parent transcript only: it blocks the lead from writing directly, but it cannot positively prove a specialist identity at write time.

## Decision

Accept the negative-gate architecture for PR1. Do not attempt to bridge parent and subagent transcripts.

Rationale:

1. **The negative gate is the high-leverage half.** The operator's actual pain (months of frustration, the May 28 commit-without-authorisation incident) is leads writing code that should have gone to a specialist. Blocking that path is what changes behaviour; positively proving the specialist's identity inside their own subagent is governance theatre — the specialist was already dispatched intentionally.
2. **Bridging transcripts would require Claude Code runtime changes.** Inheriting the parent transcript into subagent context is not in our control. Filing a feature request upstream is reasonable; gating PR1 on it is not.
3. **The positive `owner-match` path still serves a purpose.** When the orchestrator emits `[arka:dispatch] paulo -> frontend-dev` and then performs the write directly in the main thread (e.g., the orchestrator impersonating a specialist for a small touch that doesn't justify a full subagent dispatch), the path validates correctly. It also remains for forward compatibility.

## Consequences

### Positive

- PR1 ships without waiting on upstream Claude Code work.
- The dominant failure mode (lead writes specialist code in the main thread) is closed.
- The enforcer is composable with future identity mechanisms — if subagents ever inherit parent context, the positive path activates automatically without code changes.

### Negative / Acknowledged

- **The enforcer cannot tell a dispatched specialist from a lead with no routing context.** Both look like `no-routing-tag`. The operator should not interpret a clean telemetry log as proof that all writes came from authorised specialists — only as proof that no lead wrote a blocked file in the main thread.
- **Future PRs in the Squad Intelligence Upgrade must not assume positive identity proof.** PR3 (QG → Agent Memory) and PR5 (DNA Fidelity Check) need a different identity surface (likely the `Task` tool's `subagent_type` argument, which is visible to the dispatching side).

### Telemetry

`specialist_enforcer.record_telemetry` records every gated decision including `no-routing-tag`. The operator can monitor the rate of `no-routing-tag` decisions on file-mutation tools via `python -m core.governance.specialist_telemetry_cli today|week|month|all`. A persistently high `no-routing-tag` rate indicates either (a) subagent activity (expected), or (b) leads bypassing the routing marker (a separate compliance failure caught by the existing flow-marker gate).

## Mitigations

1. **`dispatch-must-be-announced` constitution rule** (added in PR1) requires leads to emit `[arka:dispatch]` before every `Agent` call. This gives the operator audit visibility of *who was supposed to be dispatched*, even when the subagent itself cannot prove it executed.
2. **The bypass marker `[arka:specialist-bypass <reason>]`** with mandatory reason is logged. Empty reasons are rejected. Bypasses land in `~/.arkaos/telemetry/specialist-dispatch.jsonl`, read by `arka-py -m core.governance.specialist_telemetry_cli` ("Bypasses used") — neither `/arka status` nor `/arka compliance` reads that log (corrected in P0.2: the original text pointed at summaries that structurally cannot show the bypass).
3. **The KB-first gate (PR16/PR17) and flow-marker gate (PR11)** continue to operate. They catch the orthogonal compliance failures (no research, no routing). Specialist enforcement composes with them, not in place of them.

## Alternatives Considered

### A. Sniff the parent transcript from the subagent

Reject. Claude Code provides no public mechanism for a subagent to access the parent transcript. Forging access via env vars or shared files is a brittle, security-suspect path.

### B. Inject the dispatch marker into the subagent's initial prompt

Possible but operationally fragile — relies on every `Agent` call carrying the marker into the prompt body, which the orchestrator may forget. Without compile-time enforcement, this becomes another advisory rule that fails the way the original problem failed.

### C. Gate `Task` itself with ownership

Considered. Rejected because `Task` is the *dispatch* primitive; gating it would block dispatches when no specialist owner exists for the file (common case: dispatching for research, planning, or non-file work). Wrong tool, wrong abstraction.

### D. Wait for upstream Claude Code parent-context exposure

Reject as the gating decision for PR1. Track upstream feature request, but ship the negative gate now. When upstream support arrives, the positive path activates by default.

## Acceptance

This ADR is the explicit acknowledgement that future PRs in the Squad Intelligence Upgrade series do not get to assume positive identity proof on specialist writes. Reviewers must verify that any positive-identity reliance in PR3, PR5, etc. uses a surface other than the PreToolUse transcript (e.g., the `subagent_type` argument captured at dispatch time, or hook-emitted dispatch records).

## Amendment (P0.2, 2026-07-13 — specialist-gate fail-open)

The blanket `no-routing-tag` ALLOW this ADR describes measured **72% of
all specialist telemetry** (4,093 of 5,683 records): a marker rolling out
of the 20-message window reopened the gate — routing once and hammering
the gate with noise was a winning strategy. P0.2 closes the eviction
hole with persist-on-observe + consult-before-allow
(`core/workflow/specialist_authorization.py`, mirroring the frontend
gate's `design_authorization`, #297) and splits `no-routing-tag` into:

- `never-routed` — session never emitted a marker; keeps the ALLOW this
  ADR documents (hardening it is a separate, telemetry-gated decision);
- `subagent-scope` — sidechain evaluation; the pass-through this ADR
  accepted, now measurable on its own;
- restored decisions — persona re-applied from persistence, carrying
  `persona_source: "persisted"` in telemetry, deciding exactly as if the
  marker were visible (including BLOCK).

The window itself now counts main-scope messages only
(`core/workflow/transcript_scope.py`), and the persisted record is keyed
by session **and transcript file name**, so a dispatched subagent — which
runs on its own transcript — can never inherit the parent's persona and
be blocked from files it was dispatched to write. The acceptance clause
above still stands: none of this proves positive identity on subagent
writes.
