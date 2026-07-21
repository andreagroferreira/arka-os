---
name: build-fix
description: >
  Systematic build-failure diagnosis: read the FIRST error bottom-up,
  reproduce it in isolation, classify it (dependency, config, code,
  toolchain, cache), fix the root cause, and prove the fix with two
  clean builds — with per-ecosystem playbooks for the failure
  signatures of Laravel/PHP, Node/TS, Vue/Nuxt, React/Next, and Python.
  TRIGGER: "/dev build-fix", "the build is broken", "o build está a
  falhar", "compila localmente mas falha no CI", "npm run build
  rebenta", "composer install falha", "arranja o build"; any red build
  whose error output exists. SKIP: the code builds but tests fail ->
  dev/code-review or dev/app-test wins; designing the pipeline itself
  -> dev/ci-cd-pipeline wins; a production outage -> dev/incident wins.
metadata:
  origin: arkaos
---

# Build Fix

> **Agent:** Paulo (Tech Lead) | **Framework:** Root-cause classification, first-error discipline

A failing build is the most honest bug report you will ever receive:
deterministic, reproducible, and pointing at itself. Almost every hour
lost to a broken build is lost the same way — fixing the LAST error on
the screen, which is usually a cascade symptom of the first one, or
reaching for the folk remedy (delete the lockfile, clear every cache,
reinstall the world) before reading what the tool actually said.

## Method

1. **Find the first error.** Scroll past the cascade; the root error is
   the earliest one, and everything after it is noise until proven
   otherwise.
2. **Reproduce in isolation.** Run the failing step alone, from a clean
   shell, with the project's pinned tool versions. A build that only
   fails inside CI is still reproducible — replicate the CI's inputs
   (env vars, lockfile, node/php/python version) locally before
   touching anything.
3. **Classify** the root error into exactly one bucket:
   | Bucket | Signature |
   |---|---|
   | Dependency | resolver conflicts, missing package, lockfile drift |
   | Config | tool config rejects input, wrong paths, env var absent |
   | Code | type error, syntax error, failed macro/codegen |
   | Toolchain | wrong runtime version, missing system binary |
   | Cache | passes clean, fails incrementally (or the reverse) |
4. **Fix the root, not the symptom.** A cast that silences a type error
   the compiler was right about is a deferred production bug.
5. **Prove it.** Two consecutive clean builds — one incremental, one
   from clean — with exit codes on record. One green build after a
   cache clear proves nothing about the fix.

## Ecosystem playbooks

### Laravel / PHP

- `Class not found` after moving a file → regenerate the autoload map
  (`composer dump-autoload`); if it persists, the namespace does not
  match the path — fix the namespace, not the autoloader.
- `composer install` resolver conflict → read WHICH two constraints
  collide before touching version pins; widening the wrong one
  downgrades half the tree.
- Migration failure mid-build → the schema state is now ahead of the
  migration table; inspect before re-running, never loop `migrate:fresh`
  on shared databases.

### Node / TypeScript

- `tsc` errors that runtime never hits → the types drifted from the
  code; fix the types, do not add `as any` (the compiler is the only
  reviewer that reads every call site).
- Works locally, fails in CI → lockfile drift: CI runs `npm ci` (exact
  lockfile) while local `npm install` mutated it. Commit the lockfile
  the build actually needs.
- `ERR_REQUIRE_ESM` / `Cannot use import` → an ESM-only dependency in a
  CJS context; align the importing module's format instead of pinning
  the dependency to a dead major.

### Vue / Nuxt

- Auto-import resolution failures (`X is not defined` only in build) →
  the dev server tolerates what nitro's build does not; add the
  explicit import.
- Hydration-safe code that fails at BUILD time in SSR → browser-only
  API executed at module top level; move it inside a lifecycle hook or
  guard it.

### React / Next.js

- Server/client boundary violations (`useState in a Server Component`)
  → mark the leaf `"use client"`, never the whole tree — pushing the
  directive up quietly moves the entire subtree to the client bundle.
- Build-time data fetching failures → a page assumed a runtime env var
  at static-generation time; decide dynamic vs static explicitly.

### Python

- Import works in the repl, fails in the build → the venv the build
  uses is not the venv you activated; print `sys.executable` in the
  failing context before debugging imports.
- Resolver backtracking forever → over-constrained pins; loosen the
  pins you own, never the transitive ones.
- Circular import only at build/collect time → the cycle was always
  there; imports inside functions defer it, moving the shared symbol
  out removes it.

## Output

```markdown
## Build Fix Report

**Failing step:** {command} · **First error:** {file}:{line} — {message}
**Bucket:** {dependency|config|code|toolchain|cache}
**Root cause:** {one sentence}
**Fix:** {what changed and why it addresses the root}
**Proof:** incremental build exit 0 · clean build exit 0 (commands on record)
```

A build fixed without the two-build proof, or a symptom silenced with a
cast or a cache clear, does not close this skill.
