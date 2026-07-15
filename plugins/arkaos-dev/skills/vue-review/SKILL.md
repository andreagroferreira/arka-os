---
name: vue-review
description: >
  Vue 3 / Nuxt review for the framework's own traps — lost reactivity,
  SSR hydration mismatches, missing keys, uncleaned watchers, and props
  mutated in place — with the fix each needs. Composition API and
  TypeScript assumed. TRIGGER: "/dev vue-review", "review this Vue",
  "review the Nuxt", "revê este componente Vue", "revê o composable",
  "porque é que a reactividade não funciona?", any diff touching
  *.vue/composables. SKIP: language-agnostic review -> dev/code-review
  wins; a handler-ordering/state-cancellation bug -> dev/click-path-audit
  wins; visual/brand review -> brand/design-review wins.
metadata:
  origin: arkaos
---

# Vue Review

> **Agent:** Diana (Senior Frontend Developer) | **Framework:** Vue 3 Composition API, Nuxt SSR, reactivity correctness

Most Vue bugs are not wrong logic — they are the reactivity system doing
exactly what you told it, which was not what you meant. Destructure a
`reactive` object and the binding is gone; read a value during SSR that
only exists on the client and hydration tears; forget a `:key` and the
list reuses the wrong DOM. This review reads a Vue/Nuxt diff for those
framework-specific traps, on the assumption of Composition API and
TypeScript throughout.

## Review Priorities

### Critical — Reactivity
- **Destructured reactivity**: `const { x } = reactive(...)` or a destructured prop → `toRefs`/`toRef`, or access through the object; the destructured copy is inert.
- **Ref unwrapped wrong**: `.value` missing in script, or added in template; a `ref` stored in a plain object it is read from without unwrapping.
- **Prop mutated in place** → emit an event or use a local copy; props are one-way.

### Critical — SSR / Nuxt hydration
- **Client-only value read during SSR** (`window`, `localStorage`, `Date.now()` in setup) → guard with `import.meta.client`/`onMounted`; the mismatch tears hydration.
- **Non-deterministic render** between server and client (random, unstable order).
- **Data fetched without `useAsyncData`/`useFetch`** where SSR needs it → double fetch or hydration gap.

### High — Correctness
- **Missing `:key`** on a `v-for`, or `:key="index"` on a reorderable list → wrong-DOM reuse.
- **Watcher/interval/listener not cleaned up** in `onUnmounted` → leak.
- **`v-if` + `v-for` on the same element**; heavy work in a computed with side effects.

### High — Standards
- Options API in new code where the project is Composition API; `any`-typed props; a composable that is not prefixed `use` or leaks state across instances.

## Process

1. `git diff -- '*.vue'` plus changed composables to scope the change.
2. Read each component's `setup`/template against the priorities, reactivity first.
3. Trace any SSR-sensitive value from setup to template.

## Proactive Triggers

Surface these WITHOUT being asked:

- a destructured `reactive`/props in the diff → the binding that is now dead and the `toRefs` fix
- a `window`/`localStorage`/`Date` read in `setup` of an SSR page → the hydration mismatch it causes
- a `v-for` with no `:key` or a keyed index on a list that reorders → the DOM-reuse bug

## Output

```markdown
## Vue Review

**Scope:** {changed components / composables}
**Verdict:** {APPROVED / CHANGES REQUESTED}

### Critical
- [ ] {file}:{line} — {the reactivity/SSR trap} → {the fix}

### High
- [ ] {file}:{line} — {the issue} → {the fix}

### Positive
{what handles reactivity and SSR correctly}
```
