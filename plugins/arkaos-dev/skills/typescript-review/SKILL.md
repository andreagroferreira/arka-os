---
name: typescript-review
description: >
  TypeScript/Node review for the holes the compiler waves through — `any`
  and unsafe casts, unhandled promise rejections, missing input validation
  at the boundary, and injection in queries or shell calls — with the fix
  each needs. TRIGGER: "/dev typescript-review", "review this TS", "review
  the Node", "revê o TypeScript", "revê este endpoint Node", "isto está
  type-safe?", any diff touching *.ts/*.tsx server or API code. SKIP:
  language-agnostic pre-merge review -> dev/code-review wins; React/Vue
  component rendering bugs -> dev/vue-review or dev/click-path-audit wins;
  type-design depth -> dev/type-design-analyzer wins.
metadata:
  origin: arkaos
---

# TypeScript Review

> **Agent:** Vera (Node.js / TypeScript Backend Specialist) | **Framework:** Type safety, async correctness, boundary validation

TypeScript's guarantees stop at the edges of the program, and that is
where the bugs get in: an `any` erases every check downstream, a JSON
body typed as its interface is a lie until something validates it, a
floating promise swallows the error the caller needed. This review reads
a TS diff for the places the type system was told to look away, and for
the async and boundary mistakes no compiler flags.

## Review Priorities

### Critical — Type safety holes
- **`any` / `as` casts** on external data → validate into a real type (Zod, a type guard); an `any` is an unchecked check for everything it touches.
- **Non-null `!`** on a value that can be null at runtime → handle the null.
- **`@ts-ignore` / `@ts-expect-error`** hiding a real type error → fix the type, do not silence it.

### Critical — Async correctness
- **Floating promise**: an `async` call with no `await` and no `.catch` → the rejection is lost.
- **`await` in a loop** where `Promise.all` is correct → serial latency; and the reverse, unbounded `Promise.all` over a large list.
- **Missing try/catch** around an `await` on I/O, or a catch that swallows.

### Critical — Boundary
- **Unvalidated input**: a request body/query/param used as its TS type with no runtime schema → validate at the boundary.
- **Injection**: string-built SQL or `exec`/`child_process` with user input → parameterise / sanitise.
- **Secrets**: hardcoded keys; secrets logged.

### High — Standards
- Public function signatures untyped or returning inferred `any`.
- `Promise<void>` swallowing a result the caller needs; error thrown as a bare string.
- Mutating a shared object where an immutable update belongs.

## Process

1. `git diff -- '*.ts' '*.tsx'` to scope the change.
2. Run `tsc --noEmit` and the linter if configured — read the output.
3. Read each changed handler/service for the priorities, type holes first.

## Proactive Triggers

Surface these WITHOUT being asked:

- a request body used as `req.body as SomeType` with no validation → the boundary hole and the schema that closes it
- an `async` function called with no `await`/`.catch` → the floating rejection
- an `any` introduced in the diff → what it stops the compiler from checking downstream

## Output

```markdown
## TypeScript Review

**Scope:** {changed TS}
**Verdict:** {APPROVED / CHANGES REQUESTED}

### Critical
- [ ] {file}:{line} — {the hole} → {the fix}

### High
- [ ] {file}:{line} — {the issue} → {the fix}

### Positive
{what is genuinely type-safe and correct}
```
