---
name: dev/type-design-analyzer
description: >
  Scores whether a module's types make illegal states unrepresentable —
  across encapsulation, invariant expression, invariant usefulness, and
  type-system enforcement — and names the concrete bug each weak type
  lets through. TRIGGER: "/dev type-design-analyzer", "type design",
  "illegal states", "make invalid states unrepresentable", "domain
  modelling review", "revê o design dos tipos", "estes tipos estão bem
  desenhados?"; run on the public types of a module or a domain model.
  SKIP: general code review -> dev/code-review wins; the data-model
  schema of a new feature -> dev/db-design or dev/ddd-model wins.
allowed-tools: [Read, Grep, Glob]
metadata:
  origin: arkaos
---

# Type Design Analyzer — `/dev type-design-analyzer`

> **Agent:** Gabriel (Software Architect) | **Framework:** Make-illegal-states-unrepresentable, type-driven design

The strongest bug fix is the one that makes the bug impossible to write.
A type that admits only valid values turns a whole class of runtime error
into a compile error nobody can ship past. This lens reads the shape of a
module's data — its enums, its models, its bounded fields — and asks what
invalid state that shape still permits, because every permitted invalid
state is a bug waiting for the caller who constructs it.

## Evaluation Criteria

For each type in scope, score four dimensions and justify each score
with the specific state it does or does not prevent.

| Dimension | The question |
|-----------|--------------|
| **Encapsulation** | Are internals hidden? Can an invariant be violated from outside — a public field mutated past a bound, a list appended to past its cap? |
| **Invariant expression** | Do the types encode the business rule? Is an impossible state (a shipped order with no address, a negative price) representable at all? |
| **Invariant usefulness** | Do these invariants prevent *real* bugs in this domain, or are they ceremony that constrains nothing anyone would get wrong? |
| **Enforcement** | Is the invariant enforced by the type system, or by a convention with an easy escape hatch (a raw `str` where an enum belongs, an `Optional` that is never `None` in practice but the checker cannot know)? |

## Process

1. Grep the module for its public types — dataclasses, Pydantic models, enums, TypedDicts, the domain nouns.
2. For each, ask the one diagnostic question: **what invalid value can I construct with this type that the domain forbids?** Every answer is a design gap.
3. Prefer the fix that moves the check to construction time — a validator, a narrower type, a smart constructor — over a runtime guard the caller must remember.

## Proactive Triggers

Surface these WITHOUT being asked:

- a domain value carried as a bare `str`/`int` where an enum or a bounded newtype belongs → the illegal value it now admits
- an `Optional`/nullable field that is never legitimately empty → make it required and delete the downstream `None` checks
- a boolean pair that encodes a state machine (`is_draft` + `is_published` both settable true) → the impossible state it allows; replace with one enum

## Output

```markdown
## Type Design Report

**Scope:** {module / types reviewed}

### {type name} — {file}:{line}
| Dimension | Score /5 | Why |
|-----------|---------|-----|
| Encapsulation | {n} | {the state it lets outside code violate, or "hidden"} |
| Invariant expression | {n} | {the impossible state it does/does not prevent} |
| Invariant usefulness | {n} | {real bug prevented, or ceremony} |
| Enforcement | {n} | {type-enforced, or the escape hatch} |

**Overall:** {one line} · **Fix:** {the narrower type / validator / smart constructor}
```
