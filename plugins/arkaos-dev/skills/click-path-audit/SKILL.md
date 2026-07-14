---
name: click-path-audit
description: >
  Simulates every interactive handler call-by-call to find bugs a normal
  read skips over — shared-state side effects, handlers that silently undo
  each other, and async races — then checks the final UI state matches
  what the control promises. TRIGGER: "/dev click-path-audit", "the button
  does nothing", "state side effects", "handlers cancel each other", "why
  is the UI wrong after clicking", "o botão não faz nada", "audita o fluxo
  de cliques"; run on an interactive component whose behaviour is wrong but
  whose code looks right. SKIP: general pre-merge review ->
  dev/code-review wins; visual/layout/brand review ->
  brand/design-review wins.
metadata:
  origin: ecc-derived
  source: https://github.com/affaan-m/ecc
  license: MIT
---

# Click-Path Audit

> **Agent:** Diana (Senior Frontend Developer) | **Framework:** Handler state-tracing, shared-state side-effect analysis

Some interface bugs survive every check that looks at one thing at a time.
Each handler compiles, each function returns the right type, each call
works when you test it alone — and the button still does the wrong thing,
because the second call quietly resets the state the first one set. This
lens catches those by simulating the handler on paper: it walks the calls
in the order they run and tracks what each reads, writes, and resets in
shared state, so a cancelling side effect shows up before a user ever
clicks.

## The bug this catches

A "New Email" button called `setComposeMode(true)` then `selectThread(null)`.
Each call was correct on its own, but `selectThread` reset `composeMode`
back to false as a side effect, so the button opened nothing — no type
error, no crash, and no unit test to catch it. Tracing the two calls in
order makes the reset obvious on the page.

## Process

For every interactive touchpoint in scope (`onClick`, `onSubmit`, `onChange`, effects):

1. **Identify** the handler.
2. **Trace** each call it makes, in order.
3. For each call record: what shared state it **reads**, what it **writes**, and any **side effect** — especially a state it clears or resets that it does not obviously own.
4. **Check** whether any later call undoes a state change an earlier call made.
5. **Check** the final state matches what the control's label promises.
6. **Check** for races — async calls whose resolution order changes the outcome (a stale response overwriting a fresh one).

## Proactive Triggers

Surface these WITHOUT being asked:

- two calls in one handler that write the same store slice → which one wins, and is that intended
- a setter with a side effect that resets unrelated state (a `select`/`reset`/`clear` that touches more than its name implies) → the earlier change it silently undoes
- an `await` inside a handler with no guard against an out-of-order resolution → the stale-overwrite race

## Output

```markdown
## Click-Path Report

**Scope:** {component / area audited}

### {control / handler} — {file}:{line}
| # | Call | Reads | Writes | Side effect |
|---|------|-------|--------|-------------|
| 1 | {fn} | {state} | {state} | {reset/clear, or none} |
| 2 | {fn} | {state} | {state} | {undoes call 1's write?} |

**Promised by label:** {what the user expects} · **Actual final state:** {what happens}
**Verdict:** {works / silently broken} · **Fix:** {reorder, isolate the side effect, guard the race}
```
