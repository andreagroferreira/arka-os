---
name: opensource-release
description: >
  Takes an internal module or repo public WITHOUT taking its secrets
  with it: extract the component, scrub content AND history (secrets,
  client identifiers, internal URLs, embarrassing commits), package it
  as a standalone citizen (license, README, CI, versioning), and verify
  the published artifact with an adversarial re-scan before anyone
  else can. TRIGGER: "/dev opensource-release", "open-source this",
  "vamos abrir este módulo", "prepara isto para publicar",
  "extrai isto para um repo público", any internal-to-public extraction.
  SKIP: releasing a version of an already-public package ->
  dev/release wins; secrets hygiene inside a private repo ->
  dev/env-secrets wins; redacting a document, not a repo ->
  kb/doc-redaction wins.
metadata:
  origin: arkaos
---

# Open-Source Release

> **Agent:** Bruno (Security Engineer) | **Framework:** History-aware scrubbing, adversarial pre-publication review

Publishing is the one deploy you cannot roll back. The moment a repo
goes public, every commit it ever had goes public with it — the API key
someone removed in 2024 but never rotated, the client name in a test
fixture, the TODO that names an unshipped product. Mirrors and scrapers
archive within minutes; deleting the repo afterwards deletes your copy,
not theirs.

## Phase 1 — Extract

1. Decide the boundary: what goes public, and what the public part is
   allowed to import. An internal dependency that cannot come along
   must be replaced by an interface or the boundary is wrong.
2. Extract into a FRESH repository with a FRESH history. Carrying the
   internal git history into the public repo is the default disaster —
   the scrub target becomes every blob ever committed instead of the
   current tree. Start public history at the first public commit;
   record the internal provenance (repo + commit hash) in a private
   note, not in the public tree.

## Phase 2 — Scrub, then prove the scrub

Sweep the candidate tree for, at minimum:

| Class | Examples |
|---|---|
| Credentials | keys, tokens, connection strings, `.env*`, CI secrets |
| Identity leaks | client names, internal hostnames/URLs, employee data in fixtures |
| Business leaks | pricing internals, unshipped product names, internal roadmap refs |
| Path leaks | absolute paths exposing usernames or internal layout |

Two rules make the scrub real:

- **Scan the ARTIFACT, not the intention** — after packaging, run the
  full sweep again on the exact tarball/tree that will be published
  (the `npm pack --dry-run` + grep discipline). A scrub verified on the
  working tree and published from a different state proves nothing.
- **Found secrets get ROTATED, not just removed.** A credential that
  ever sat in a candidate tree is compromised-by-assumption; removal
  cleans the repo, rotation cleans the risk.

## Phase 3 — Package as a citizen

- LICENSE chosen deliberately (permissive vs copyleft is a strategy
  decision — route it to the operator, never default silently).
- README that stands alone: what it does, install, quickstart, no
  internal context assumed.
- CI on the public repo running the public tests; versioning from
  1.0.0 or 0.x with the same discipline as any product.
- Contribution surface decided explicitly: issues on/off, PR policy,
  security contact.

## Phase 4 — Adversarial verification

Before flipping visibility, a second pass in a fresh context reviews
the exact publishable state as a hostile outsider: what can I learn
about the company from this tree that I should not? Only after that
pass returns clean does the repo go public — and the first
post-publication act is re-running the sweep against the LIVE public
artifact.

## Output

```markdown
## Open-Source Release Report

**Component:** {name} · **Boundary:** {what ships / what stayed}
**History:** fresh (internal provenance recorded privately at {ref})
**Scrub:** {classes swept} · findings {n} · rotations {n, with owners}
**Package:** {license} · README ✓ · CI ✓ · version {v}
**Adversarial pass:** {clean / findings and their fixes}
**Published:** {url} · post-publication re-scan: {clean}
```
