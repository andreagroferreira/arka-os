---
name: silent-failure-hunter
description: >
  Hunts silent failures — swallowed exceptions, errors coerced to null,
  fallbacks that mask a broken path, lost stack traces, and unguarded
  network/file/db/transaction calls — and reports the concrete failure
  each one hides, ranked by blast radius. TRIGGER: "/dev
  silent-failure-hunter", "silent failures", "swallowed errors", "empty
  catch", "error handling review", "falhas silenciosas", "erros
  engolidos", "isto está a falhar em silêncio?"; run on the error paths
  of any change touching I/O, network, db, or transactions. SKIP: general
  pre-merge review -> dev/code-review wins; test coverage of the change ->
  dev/pr-test-analyzer wins.
metadata:
  origin: ecc-derived
  source: https://github.com/affaan-m/ecc
  license: MIT
---

# Silent Failure Hunter

> **Agent:** Rita (QA Engineer) | **Framework:** Defensive error handling, fail-loud discipline

Every catch block is a decision about who finds out when something breaks.
Too many of them decide that nobody does: the exception is caught and
dropped, the failed call returns an empty list, the timeout is swallowed
and the caller carries on with half the data. This lens assumes the worst
about each one and asks a single question of it — when this path fails at
runtime, who learns, and how?

## Hunt Targets

| # | Class | What to flag |
|---|-------|--------------|
| 1 | Swallowed errors | `catch {}`, `except: pass`, an error coerced to `null`/`[]`/`0` with no log and no re-raise |
| 2 | Inadequate logging | logged at the wrong severity, logged without the context to diagnose it, log-and-continue where the caller needed to know |
| 3 | Masking fallbacks | a default that hides a real failure — `.catch(() => [])`, `?? {}` over a failed fetch — so the bug surfaces three layers downstream instead of here |
| 4 | Broken propagation | a lost stack trace, a generic re-raise that drops the cause, an `async` path with no `await` on the error, a promise with no rejection handler |
| 5 | Unguarded boundaries | a network/file/db call with no timeout and no error handling; transactional work with no rollback on the failure path |

## Process

1. Grep the diff (or the named area) for the target patterns — `catch`, `except`, `.catch(`, `try`, `?? `, bare `return null`.
2. For each hit, answer one question: **if this path fails at runtime, who finds out, and how?** If the answer is "nobody" or "a confused engineer three files away", it is a finding.
3. Trace the caller once — a swallowed error is only safe if the caller genuinely does not need to know, and that is rare.
4. Rank by blast radius: a masked failure on a payment or data-write path is critical; a swallowed log flush is minor.

## Proactive Triggers

Surface these WITHOUT being asked:

- an empty catch on any I/O, network, or database call → critical; name what fails silently
- `.catch(() => <default>)` or `except: pass` on a data-fetch path → the downstream bug this plants is worse than the crash it prevents
- a re-raise that drops the original exception (`raise NewError()` with no `from`) → the stack trace the on-call engineer needs is gone

## Output

```markdown
## Silent Failure Report

**Scope:** {files / diff reviewed}
**Findings:** {n} ({c} critical, {h} high, {m} medium)

### {SEVERITY} — {file}:{line}
- **Hides:** {the concrete runtime failure that goes unseen}
- **Impact:** {who is affected and how far downstream the real bug surfaces}
- **Fix:** {the specific change — log with context, re-raise with cause, add the timeout}

### Clean
{paths checked that handle failure honestly — say so, briefly}
```
