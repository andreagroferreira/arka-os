---
name: dev/react-review
description: >
  React / Next.js review for the framework's own traps — stale closures
  in hooks, dependency arrays that lie, derived state stored instead of
  computed, keys that force remounts, effects doing render work, and
  server/client boundary leaks in the App Router — with the fix each
  needs. Hooks and TypeScript assumed. TRIGGER: "/dev react-review",
  "review this React", "review the Next.js", "revê este componente
  React", "revê o hook", "porque é que o efeito corre duas vezes?", any
  diff touching *.tsx components or custom hooks. SKIP:
  language-agnostic review -> dev/code-review wins; TypeScript type
  design without React specifics -> dev/typescript-review wins; a
  handler-ordering/state-cancellation bug -> dev/click-path-audit wins;
  visual/brand review -> brand/design-review wins.
allowed-tools: [Read, Grep, Glob]
metadata:
  origin: arkaos
---

# React Review — `/dev react-review`

> **Agent:** Diana (Senior Frontend Developer) | **Framework:** Hooks semantics, render-cycle discipline, RSC boundaries

Where Vue's traps announce themselves — reactivity silently lost is
still lost — React's traps ship working code that is wrong later: the
closure that captured last render's state, the dependency array that
omits what the effect reads, the memo that never invalidates. This
review walks the render cycle, not the file: what each render reads,
what it captures, and what survives to the next one.

## The traps, and the fix each needs

| # | Trap | Signature | Fix |
|---|------|-----------|-----|
| 1 | Stale closure | callback reads state captured N renders ago | functional updater (`setX(v => ...)`) or include the dep and let the callback re-create |
| 2 | Lying dependency array | effect reads `a`, deps say `[b]` | list what the effect READS; if that loops, the effect does too much — split it |
| 3 | Derived state stored | `useState` mirroring a computable value, synced by effect | compute during render (`useMemo` if costly); delete the effect |
| 4 | Key-forced remounts | `key={index}` on reorderable lists, or key changing identity every render | stable identity key; component state survives reorders |
| 5 | Effects doing render work | formatting/filtering in `useEffect` + `setState` | that is render logic — move it into render; effects are for the outside world |
| 6 | Boundary leak (App Router) | `"use client"` at the top of a tree because one leaf needs a hook | push the directive to the leaf; a client parent drags every child into the bundle |
| 7 | Context re-render storm | one broad context carrying fast-changing values | split contexts by change rate, memoize the provider value |
| 8 | Unstable references as props | inline objects/functions into memoized children | hoist or `useCallback`/`useMemo` — or drop the memo, half-memoized is unmemoized |

## Process

For every component and custom hook in scope:

1. **Trace one render**: what it reads, what it computes, what it
   captures in closures handed to children, effects, or timers.
2. **Interrogate every `useEffect`**: does it synchronize with an
   external system (fetch, subscription, DOM)? If it only moves state
   around, it is a trap-3 or trap-5 candidate.
3. **Check every dependency array against the closure it feeds** — the
   array documents what the closure reads; any omission is a latent
   staleness bug, not an optimization.
4. **Walk the server/client boundary** (Next.js App Router): where does
   `"use client"` sit, and does anything serialize a non-serializable
   prop across it?
5. **Confirm list keys carry identity**, not position.

## Proactive Triggers

Surface these WITHOUT being asked:

- an async callback using state without a functional updater → the
  stale-closure race it hides
- `useEffect` + `setState` whose only input is other state → the
  derived-state rewrite that deletes both
- a `"use client"` higher than the hook that needs it → the bundle cost
  and the RSC benefits silently forfeited

## Output

```markdown
## React Review Report

**Scope:** {components / hooks reviewed}

### {Component / hook} — {file}:{line}
**Trap:** {#N name} · **Evidence:** {what the render trace shows}
**Consequence:** {what goes wrong, when}
**Fix:** {the specific rewrite}

**Verdict:** {clean / N findings, ranked by user impact}
```
