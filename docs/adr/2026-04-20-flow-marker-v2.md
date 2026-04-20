---
id: ADR-2026-04-20-flow-marker-v2
title: Flow Marker v2 — Turn-Scoped Cache (Amendment to ADR 2026-04-17)
status: accepted
date: 2026-04-20
deciders: Andre Groferreira (owner), Marco (CTO), Marta (CQO), Paulo (Dev Lead)
amends: docs/adr/2026-04-17-binding-flow-enforcement.md
related:
  - core/workflow/flow_enforcer.py
  - core/workflow/marker_cache.py
  - config/hooks/pre-tool-use.sh
  - config/hooks/post-tool-use.sh
  - config/hooks/user-prompt-submit.sh
  - arka/skills/flow/SKILL.md
---

# ADR — Flow Marker v2 (Amendment to 2026-04-17)

## Status

Accepted — 2026-04-20

## Relationship

This is a **formal amendment** to the binding flow enforcement ADR (2026-04-17).
It does not supersede. The hybrid Layer 1 (advisory) + Layer 2 (binding)
architecture stands as originally decided. This amendment adds a
**Layer 3 — turn-scoped marker cache** that is strictly an allow-path
accelerator and preserves the original ADR's invariants.

## Context

Post-release telemetry on the binding enforcement (2026-04-17 → 2026-04-20)
surfaced a high false-positive rate for the `no-flow-marker-in-last-3-assistant-messages`
deny path. The owner reported the error firing repeatedly during
legitimate work. Forensic analysis of transcripts confirmed the following
failure modes:

1. **Subagent dilution** — a `Task` dispatch produces multiple assistant
   messages without re-emitting routing. The 3-message window covers the
   subagent exchange, pushing the parent's routing marker out of scope.

2. **Short continuations** — user prompts like "continue", "ok go", "força"
   are classified as flow-required but the model's response is brief and
   does not re-emit routing. Subsequent `Write`/`Edit` within the same
   turn hits an empty window.

3. **Tool result interleaving** — long tool results break the 3-message
   span by inserting assistant messages that are pure tool acknowledgements.

The original ADR explicitly rejected `Alt D — Full Workflow State Machine`
because of development cost. It accepted the trade-off that the 3-message
window would produce some false positives, but the actual rate in
production exceeded the assumed budget.

## Decision drivers

1. **Preserve the invariants of 2026-04-17.** Deny decisions must remain
   authoritative from the transcript. Cache may accelerate allow only.
2. **Do not reopen Alt D.** Full semantic phase state is still out of
   scope for this cycle.
3. **Zero new cross-process coordination.** The original ADR rejected
   `/tmp` state as a decision basis due to race conditions. Any new
   state must be race-safe or strictly best-effort.
4. **Rollout without behavioural break.** Existing sessions with working
   flow emission must see identical behaviour; only the failing cases
   recover.
5. **Test-gated.** The regression that motivates this ADR must be
   captured as a permanent test case.

## Alternatives considered

### Alt A — Widen the window (only)

Raise `ASSISTANT_WINDOW` from 3 to 6 or 10.

- Pros: zero new code, trivial change.
- Cons: mitigates the 3-message dilution case but does not address short
  continuations (the routing may be older than 10 messages if a turn
  contains many tool results). Also loosens the invariant that flow is
  re-affirmed per turn.
- **Partially adopted** as the cache-miss fallback (window = 6), not as
  sole solution.

### Alt B — Session-scoped persistent marker

Write the marker once when routing is emitted. Never invalidate until
session end.

- Pros: simplest write-once semantics.
- Cons: flow is conceptually per-turn (per user request). A session
  marker would allow a user to change topic entirely — e.g. from "fix
  a bug" to "send an email" — without new routing. The constitution's
  `squad-routing` rule requires per-request routing.
- **Rejected**: weakens `squad-routing`.

### Alt C — Turn-scoped marker cache (adopted)

Write marker on emission, invalidate on each `UserPromptSubmit`. Cache
is consulted in `flow_enforcer.evaluate()` as an allow accelerator only;
deny path unchanged (still stateless transcript scan with a widened
fallback window).

- Pros: matches the semantic "flow is per-turn" without adding a state
  machine. Accelerates the common path. Preserves ADR-17 invariants.
- Cons: adds one file (`marker_cache.py`), two hook edits, Windows
  parity work.
- **Adopted.**

### Alt D — Revisit semantic phase state machine (deferred, again)

Parse transcript to infer `current_phase`, gate writes on
`phase ∈ {10, 11}`.

- Pros: semantically correct.
- Cons: 8-12 dev-days; non-trivial parse; false-positive risk is the
  worst UX. Original ADR deferred this to v3.
- **Still deferred.**

## Decision

Adopt **Alt C — Turn-Scoped Marker Cache**.

### Layer 3 — Turn-Scoped Marker Cache

Add `core/workflow/marker_cache.py` with this contract:

| Aspect | Value |
|---|---|
| Storage path | `/tmp/arkaos-flow-marker/<session_id>.json` (env-override `ARKA_MARKER_CACHE_DIR`) |
| Write trigger | `PostToolUse` hook detects `[arka:routing]` or `[arka:trivial]` in `assistant_message` |
| Invalidate trigger | `UserPromptSubmit` hook (every new user prompt) |
| Payload | `{marker_type, dept, lead, turn_start_ts}` |
| Write atomicity | tmp + rename with `pid-tid-uuid` suffix (safe under 200-thread contention, multi-process safe) |
| Session id validation | `SAFE_SESSION_ID_RE` allowlist, same as `flow_enforcer.py` |
| Consumed by | `flow_enforcer.evaluate()` between `(d) flow-required check` and `(f) transcript scan` |
| Semantics | **ALLOW acceleration only** — cache absence never denies |

### Updated `flow_enforcer.evaluate()` flow

```
(a) tool in GATED_TOOLS?              no  → allow
(b) feature flag on?                  no  → allow
(c) ARKA_BYPASS_FLOW=1?               yes → allow + audit
(d) flow required for session?        no  → allow
(e) marker cache hit for session?     yes → allow  (reason: `marker-cache-hit:<type>`)   ← NEW
(f) transcript scan (window=6)        hit → allow  (reason: `marker-found:<type>`)
                                      miss → deny  (reason: `no-flow-marker-in-last-6-assistant-messages`)
```

The deny path (f) never consults the cache. The cache never produces a
deny. If cache is corrupt, missing, or stale, (f) is authoritative.

### Window change

`ASSISTANT_WINDOW` raised from `3` to `6` in `flow_enforcer.py`. Rationale:
when the cache misses (e.g. first tool call after a marker emission that
somehow failed to write to cache), the widened transcript window gives
the fallback a reasonable chance of finding the marker without inviting
the "session-scoped" trap Alt B had. Measured against transcripts of
the reported failures, 6 recovers 100% of the reported cases that had
the marker present in the same turn.

### Subagent inheritance

When `Task` dispatches a subagent, the cache is already populated from
the parent's earlier routing emission. The subagent inherits
automatically; no re-emission required. If the subagent itself emits
a new routing (e.g. delegated to a different lead), the PostToolUse
hook overwrites the cache entry atomically.

### Windows parity

`config/hooks/post-tool-use.ps1` and `config/hooks/user-prompt-submit.ps1`
mirror the bash logic using `ProcessStartInfo` with a 1.5 s timeout on
the Python subprocess. No platform is left with partial enforcement.

## Rollout

This amendment ships on the same feature branch as the `KB-First Loop`
work (`feature/intelligence-v2`). No separate flag required — the cache
is behind the same `hooks.hardEnforcement` feature flag as the rest of
the binding enforcement.

| Milestone | Action | Gate |
|---|---|---|
| v2.21.0-beta.1 | Ship cache + widened window behind `hardEnforcement` flag (default current state per install) | Full test suite green |
| Owner self-test (3 days) | Owner runs on `arka-os` + one client project | Zero `no-flow-marker-in-last-6-...` false positives |
| v2.21.0 | GA | Telemetry clean, QG approved |

## Consequences

### Positive

- Eliminates the reported false-positive class without reopening Alt D.
- Deny path remains stateless and transcript-authoritative, preserving
  ADR-17's security posture.
- Subagent and multi-turn continuations now work out of the box; users
  are not punished for legitimate flow.
- Test coverage on the fix is permanent:
  `test_evaluate_cross_turn_subagent_scenario` captures the regression.

### Negative

- Adds one new module (`marker_cache.py`) and two hook code paths. The
  surface for maintenance grows modestly.
- A corrupted cache file silently falls back to transcript scan. Users
  may see latency (additional transcript read) but never a wrong deny.
- `/tmp` cleanup is the OS's responsibility. On long-lived Codespaces or
  similar, stale marker files may accumulate. Size is trivial
  (≤ 200 bytes per session). `UserPromptSubmit` invalidates per-turn so
  each session keeps at most one entry at any time.

### Neutral

- The cache is still "cache" in the ADR-17 sense — its purpose is
  acceleration, not authority. Removing it in a future architecture
  (Alt D full state machine) does not require an API break; only the
  evaluate() function's (e) step goes away.

## Test evidence

- `tests/python/test_flow_enforcer_v2.py` — comprehensive cache + widened-window coverage, including:
  - `test_evaluate_cache_never_sole_basis_for_deny` (ADR invariant)
  - `test_evaluate_cross_turn_subagent_scenario` (the reported bug)
  - `test_marker_cache_atomic_write_concurrent` (multi-thread safety)
  - `test_marker_cache_safe_session_id_rejects_traversal` (security)
- `tests/python/test_flow_enforcer.py` — existing suite extended with window-and-cache sanity assertions.
- Coverage invariant: `flow_enforcer` and `marker_cache` modules remain ≥ 80% line coverage.

## References

- `docs/adr/2026-04-17-binding-flow-enforcement.md` — amended ADR
- `arka/skills/flow/SKILL.md` — 13-phase flow spec
- `config/constitution.yaml` — `mandatory-flow`, `squad-routing` rules
- `~/.arkaos/plans/2026-04-20-intelligence-v2.md` — parent plan
- Obsidian: `[[ArkaOS v2 Architecture Decisions]]` (ADR index),
  `[[2026-04-20 Intelligence v2 — Flow Marker + KB-First Loop]]`
