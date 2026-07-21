---
name: ops/session-retro
description: >
  Post-session friction analysis over the actual transcript: finds the
  corrections the operator made more than once, the tool loops, the
  redone work, and the vague asks that cost a round-trip — and turns
  each recurring pattern into its structural fix (a hookify predicate,
  a recipe, a refined prompt template, a missing skill). TRIGGER:
  "/ops session-retro", "analisa esta sessão", "what went wrong this
  session", "porque é que isto demorou tanto?", "retro da sessão", end
  of a long or frustrating working session. SKIP: capturing an
  APPROVED feature build for reuse -> arka-recipes wins; you already
  know the predicate to enforce -> ops/hookify wins; team/human
  retrospectives -> lead/team-health wins.
allowed-tools: [Read, Grep, Glob, Bash]
metadata:
  origin: arkaos
---

# Session Retro — `/ops session-retro`

> **Agent:** Daniel (Operations Lead) | **Framework:** Transcript friction mining, pattern-to-fix routing

You shipped. The tests are green, the PR is merged, and nobody asks
what the session cost to get there — the correction typed three times,
the file re-read five, the plan that bounced twice for the same reason.
That cost repeats next session, and the one after, until someone reads
the transcript looking for it. The deliverable was reviewed; the
PROCESS never is. This is that review.

## Mine the transcript

Sources, in order of reliability: the session transcript itself, the
telemetry the hooks recorded during it (`~/.arkaos/telemetry/` —
stop-lint events, tool-loop detections, compliance lines), and the git
reflog of the period. Findings must quote their instances — a friction
claim without at least two concrete occurrences is an anecdote and is
reported as such or dropped.

| Pattern | Signature in the transcript |
|---|---|
| Repeated correction | operator states the same guidance ≥2 times, any phrasing |
| Tool loop | same call, same target, no state change between (the tool-loop detector's events, plus manual scan) |
| Redone work | an artifact written, then rewritten from scratch after a bounce that named a knowable-in-advance defect |
| Vague-ask round-trip | request → clarification exchange → the ACTUAL request (the refine pattern, observed after the fact) |
| Context churn | the same file read repeatedly far apart — a sign the fact belonged in memory or a doc |

## Route each pattern to its structural fix

The retro's output is not a list of regrets — every confirmed pattern
maps to exactly one fix owner:

- Repeated correction with a decidable predicate → **ops/hookify**
  (hand it the instances; they are the evidence Step 1 needs).
- Correction that needs judgment → memory entry or department skill
  gap, named explicitly.
- Redone work after a preventable bounce → the checklist/skill that
  would have caught it BEFORE the first attempt.
- Vague-ask round-trips → the prompt template or refine flow that
  front-loads the missing parameters.
- Context churn → the doc, memory, or CLAUDE.md line where the fact
  should permanently live.

A pattern with no viable fix is stated as accepted cost — visible,
priced, and chosen, rather than silently paid again.

## Output

```markdown
## Session Retro — {session/date}

**Shipped:** {what the session delivered} · **Friction cost:** {rough
turns/time attributable to the patterns below}

| # | Pattern | Instances | Fix | Owner |
|---|---|---|---|---|
| 1 | {repeated correction: "stage by explicit path"} | {turn refs} | hookify predicate | ops/hookify |

**Accepted costs:** {none, or the priced list}
**One change for next session:** {the single highest-leverage fix}
```
