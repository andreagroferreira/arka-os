# ADR: Phantom-action check stays warn-only (promotion criterion defined)

- **Date:** 2026-07-09
- **Status:** Accepted (operator-delegated backlog decision, consolidation
  session 2026-07-09)
- **Relates to:** `core/governance/phantom_action_check.py` (prompt-surface
  P0 2026-07-08), PR #261 (FP-class closure), constitution rule
  `evidence-flow`.

## Context

The phantom-action check (a response-side classifier that flags prose
claiming a completed EFFECT — "criei o ficheiro X", "I pushed the fix" —
in a turn with zero tool_use blocks) shipped warn-only, with promotion to
hard enforcement explicitly deferred "pending telemetry". PR #261 closed
the known false-positive class (analytic/mental nouns) and left two
residuals as strict-xfail trackers: **M2** is a false *negative* (a
second effect verb in the same clause escapes detection — recall loss,
harmless under any mode), while **M3** is a residual false *positive*
(analytic-synonym tail: "I updated my read on the file" still yields a
claim) — the exact class that would wrongly block under enforcement.

The telemetry verdict, read on 2026-07-09 from
`~/.arkaos/telemetry/enforcement.jsonl`:

- **27** stop-hook events carry phantom fields since instrumentation.
- **27/27** `phantom_check_passed: true`, reason `no-claims`.
- **0** flagged claims — before or after the #261 fix (post-fix sample:
  2 events).

A second, structural finding: the stop hook writes the phantom result to
`arkaos-phantom` tmp state, but **no component consumes that state**.
"Promotion" is therefore not a config flip — it means designing and
building a new blocking path (stop-hook retry injection or PreToolUse
gate) that does not exist today.

## Decision

**Keep the phantom-action check warn-only.** Do not build the
enforcement consumer now.

Rationale:

1. **Zero live positives.** The detector has never flagged a claim in
   production telemetry. An enforcement path would be dormant machinery
   with real blast radius (blocking the Stop hook) and no validated
   benefit — speculative infrastructure, which `excellence-mandate`
   does not require and evidence-based governance argues against.
2. **The post-fix sample is 2 events.** Even if we wanted promotion,
   n=2 cannot certify the #261 FP fix under real load.
3. **A known false-positive residual is still open.** M3 (the
   analytic-synonym tail, locked as strict xfail in
   `test_phantom_action_check.py`) proves the detector can still invent
   a claim from response prose. Under warn-only that costs a log line;
   under enforcement it would wrongly block a legitimate turn. Promoting
   before closing M3 would ship a known wrong-block. (M2, the recall
   residual, only under-detects and gates nothing.)

## Promotion criterion (when to revisit)

Revisit promotion when the telemetry accumulates **≥ 5 flagged claims**
(any `phantom_check_passed: false` events). At that point:

1. Manually review every flagged claim against its transcript.
2. If precision ≥ 4/5 (at most one FP), design the blocking consumer
   (stop-hook retry with the flagged claim quoted back to the model) as
   its own PR with tests.
3. If precision < 4/5, close the new FP class first (the #261 pattern:
   reproduce, extend the pattern, lock with tests) and reset the count.

Until the counter moves, the check keeps earning its keep as telemetry:
every event proves the classifier ran against a real closing message.

## Consequences

- No new code now; `stop.py` and `phantom_action_check.py` unchanged.
- The unused `arkaos-phantom` tmp state stays as the pre-built handoff
  point for the future consumer (cheap to keep, documented here).
- The M2/M3 xfail trackers in the test suite remain the backlog marker
  for detector completeness work; closing M3 (the FP tail) is a hard
  prerequisite of any future promotion, per the criterion above.
