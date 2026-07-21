---
name: epic-coordination
description: >
  Turns an epic into a coordinated set of GitHub issues with an explicit
  dependency graph, then drives it: sweep for unblocked work, dispatch
  in dependency order, keep issue state honest against merged reality,
  and close the epic only when the graph is empty. TRIGGER: "/pm epic",
  "break this epic into issues", "parte isto em issues", "coordena
  estes issues", "what can start now?", "o que está desbloqueado?",
  multi-PR work spanning more than one workstream. SKIP: sizing and
  cadence for a sprint -> pm/sprint-plan wins; writing one story well
  -> pm/story-write wins; branch/merge discipline within a single
  change -> ops/github-ops wins; ranking the backlog -> pm/backlog-groom
  wins.
metadata:
  origin: arkaos
---

# Epic Coordination

> **Agent:** Carolina (Product Manager) | **Framework:** Dependency-graph decomposition, single-source issue state

An epic dies in one of two ways: as a monolith pull request nobody can
review, or as twenty issues nobody sequenced — where three developers
block each other by lunchtime and the "done" column fills with work
that cannot ship because its dependency never started. Both deaths have
the same cause: the dependencies existed, but only in someone's head.

## Phase 1 — Decompose against the graph

1. Break the epic into issues where each issue is **independently
   mergeable**: it can go to master alone without breaking the build,
   even if the feature is not yet user-visible behind it.
2. For each issue record what it **blocks** and what it is **blocked
   by**. A dependency that cannot be named in one sentence ("B reads
   the schema A creates") is usually a sign the split is wrong — re-cut
   the boundary before creating anything.
3. Write the graph INTO the issues (`gh issue create` with "Blocked by
   #N" / "Blocks #N" in the body, labels for the epic and workstream).
   GitHub is the single source of state — a graph kept in a document
   diverges from reality by the second merge.

## Phase 2 — Drive by sweep

Repeat until the graph is empty:

1. **Sweep**: an issue is *unblocked* when every "Blocked by" reference
   is closed AND its commits are actually on the target branch —
   closed-but-unmerged is still blocked, whatever the issue state says.
2. **Dispatch** every unblocked issue; independent issues run in
   parallel, dependent ones never do.
3. **Reconcile** after each merge: close what merged, update "Blocked
   by" lists the merge invalidated, and re-sweep. Reality moves the
   graph; the graph never moves reality.
4. **Escalate stalls**: an issue unblocked for longer than the epic's
   agreed cadence with no movement is a decision waiting to be made —
   name it to the operator instead of letting the graph silt up.

## Invariants

- Every issue names its epic; the epic issue links every child. Orphan
  work inside an epic is scope creep with a paper trail.
- The critical path (longest dependency chain) is stated in the epic
  issue and re-derived after every reconcile — priorities follow it,
  not the order issues were created in.
- Closing the epic requires the graph empty AND the epic's acceptance
  line verified against the merged state, not against the issue list.

## Output

```markdown
## Epic Status — {epic title} (#{epic issue})

**Issues:** {open}/{total} · **Critical path:** #{a} → #{b} → #{c}
**Unblocked now:** #{n}, #{m} · **Blocked:** #{x} (by #{y})
**Stalled:** {none, or issue + the decision it waits on}
**Next dispatch:** {what starts now, in what order, and why}
```
