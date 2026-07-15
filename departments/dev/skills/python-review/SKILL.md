---
name: dev/python-review
description: >
  Python review against ArkaOS conventions — missing type hints, mutable
  default arguments, bare excepts, unvalidated boundaries, injection, and
  Pydantic/FastAPI mistakes — with the fix each needs. TRIGGER: "/dev
  python-review", "review this Python", "review the FastAPI", "revê o
  Python", "revê este endpoint", "isto está pythonico?", any diff touching
  *.py. SKIP: language-agnostic pre-merge review -> dev/code-review wins;
  pytest coverage of the change -> dev/pr-test-analyzer wins; swallowed-error
  hunt across the codebase -> dev/silent-failure-hunter wins.
allowed-tools: [Read, Grep, Glob, Bash]
metadata:
  origin: arkaos
---

# Python Review — `/dev python-review`

> **Agent:** Diogo (Python Backend Specialist) | **Framework:** Type hints, Pydantic validation, PEP 8, ArkaOS core conventions

Python trusts the author, and that trust is where the bugs live: a
mutable default argument shared across every call, a bare `except` that
buries the traceback, a function with no type hints that the checker
cannot help. This review reads a Python diff against the ArkaOS core
standard — type hints on every signature, Pydantic at the boundary,
functions under thirty lines — and for the runtime traps the interpreter
will happily let ship.

## Review Priorities

### Critical — Correctness traps
- **Mutable default argument**: `def f(x=[])` / `={}` → default to `None`, build inside.
- **Bare `except:` / `except Exception: pass`** → catch the specific type, log, re-raise or handle.
- **Late-binding closure in a loop** capturing the loop variable → bind explicitly.

### Critical — Boundary & security
- **Unvalidated input** used as a trusted shape → a Pydantic model at the boundary, not a raw dict.
- **Injection**: f-string/`%`-built SQL or `subprocess`/`os.system` with user input → parameterise / `shlex`, never interpolate.
- **`eval`/`exec`/`pickle`** on untrusted data; hardcoded secrets.

### High — ArkaOS core standard
- **Missing type hints** on a public signature → hint params and return.
- **A function over 30 lines** or nesting past 3 → decompose (`.claude/rules/python-core.md`).
- **Pydantic misuse**: validation logic in a route instead of a `field_validator`; a model that admits an illegal state.
- **Dataclass over Pydantic** where validation is needed; a broad `dict`/`Any` where a model belongs.

### High — Idiom
- A manual index loop where a comprehension/`enumerate` reads clearer; a `try` used for flow control; string concatenation in a hot loop.

## Process

1. `git diff -- '*.py'` to scope the change.
2. Run `ruff`/`mypy`/`pytest` if configured — read the output, do not just note their absence.
3. Read each changed function against the priorities, correctness traps first.

## Proactive Triggers

Surface these WITHOUT being asked:

- a mutable default argument in the diff → the shared-state bug across calls
- a `dict` passed through several layers as if typed → the Pydantic model that should guard the boundary
- a function that grew past 30 lines in the diff → the seam to split it on

## Output

```markdown
## Python Review

**Scope:** {changed Python}
**Verdict:** {APPROVED / CHANGES REQUESTED}

### Critical
- [ ] {file}:{line} — {the trap} → {the fix}

### High (ArkaOS standard)
- [ ] {file}:{line} — {the convention broken} → {the fix}

### Positive
{what is idiomatic and well-typed}
```
