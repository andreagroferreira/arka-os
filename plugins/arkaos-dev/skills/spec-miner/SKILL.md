---
name: spec-miner
description: >
  Mines a spec OUT of an existing codebase: maps entry points into
  capabilities, samples the code under an explicit token budget, and
  emits machine-parseable WHEN→THEN requirements and invariants — with
  uncertainty marked, nothing invented, and the source commit recorded so
  the spec knows when it has aged. TRIGGER: "/dev spec-miner", "extrai a
  spec", "reverse-engineer the spec", "what does this code actually do,
  as requirements", "documenta o comportamento existente", brownfield
  onboarding, and always BEFORE refactoring code that has no spec. SKIP:
  spec for something new -> dev/spec wins (greenfield WHAT); a guided
  tour of the codebase -> dev/codebase-onboard wins; library or
  framework evaluation -> dev/research wins.
metadata:
  origin: arkaos
---

# Spec Miner

> **Agent:** Gabriel (Architect) | **Framework:** Living Specs, budgeted behavioral sampling

`arka-spec` answers "what should we build?" before code exists. This
skill answers the inverse — "what did we already build?" — for the far
more common case: a working system whose only specification is the code
itself, about to be refactored by someone who cannot afford to be wrong
about current behavior.

## Phase 1 — Map

Detect the structure and group entry points into capabilities: HTTP
routes, CLI commands, queued jobs, scheduled tasks, event handlers,
public package exports. Each capability gets a name and its entry files.
No code reading yet — this phase is inventory, and it bounds phase 2.

## Phase 2 — Sample and expand, under budget

Reading everything is a trap: the budget burns on utilities while the
behavior lives at the surface. So:

1. Read the entry and facade files of each capability first — in most
   codebases they encode ~70% of observable behavior.
2. Descend ONE level into the call chain, only where the facade defers a
   decision (validation, branching, persistence rules).
3. **Stop** at external boundaries (SDKs, frameworks, network) or at 15
   files per capability, whichever comes first.
4. Whatever was deferred is listed in the spec as explicitly unmined —
   deferred scope is visible scope, never silent scope.

## Phase 3 — Emit

Requirements in WHEN→THEN form, invariants as standalone guarantees, both
machine-parseable, written as a markdown document that sits beside the
authored specs in `core/specs/`:

```markdown
### Requirement: {capability} — {behavior}
WHEN {trigger and preconditions}
THEN {observable outcome}
<!-- source: {file}:{lines} -->

### Invariant: {guarantee}
<!-- source: {file}:{lines} -->
```

Three hard rules:

- **Never invent behavior.** If the code is ambiguous, write the
  requirement with an `<!-- uncertainty: {what is unclear} -->` marker
  instead of a guess. A wrong spec is worse than a gap — the gap gets
  investigated, the wrong spec gets trusted.
- **Every claim carries a source pointer.** A requirement nobody can
  trace to a file and line is an opinion.
- **Stamp the mined commit hash** in the spec frontmatter. When HEAD
  moves, the spec's age is measurable with a single
  `git log <hash>..HEAD`, so drift is visible instead of quiet.

## Output

The mined spec is a markdown document beside the authored ones, and
`status: mined` in its frontmatter is a proposed convention, not an
engine state: it stays `mined` until a human reviews the document and
changes the status by hand. The report ends with the coverage summary —
capabilities mined, files read vs. deferred, uncertainty count — so the
reader knows exactly how much of the system the spec actually saw.
