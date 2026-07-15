---
name: github-ops
description: >
  Drives git and GitHub operations under the branch-isolation and
  evidence rules — isolated branch, staging by explicit path, a PR whose
  CI is proven CLEAN before any merge, and a verified push — never a merge
  on a still-pending check. TRIGGER: "/ops github-ops", "open a PR",
  "merge when green", "is this safe to merge", "abre um PR", "faz merge
  quando o CI passar", "cria a branch e o PR", "confirma os checks"; use
  for the branch → commit → PR → merge lifecycle of a change. SKIP: the
  version-bump/tag/npm-publish release pipeline -> dev/release wins; a
  CI/CD deploy to infrastructure -> dev/deploy wins; running arbitrary
  non-git shell steps -> ops/terminal-ops wins.
metadata:
  origin: arkaos
---

# GitHub Ops

> **Agent:** Daniel (Ops Lead) | **Framework:** Branch-isolation (NON-NEGOTIABLE), evidence-flow, merge-on-green

"I opened the PR" and "the PR is mergeable with every check green" are
not the same sentence, and treating them as one is how a red build lands
on the default branch. A merge fired while CI was still `pending`, a
`git add -A` that swept an unrelated file into the commit, a force-push
that quietly rewrote a teammate's history — each is a git operation that
*ran* without being *verified*. This skill drives the branch → commit →
PR → merge lifecycle so that every step is isolated and proven: staged by
explicit path, pushed and confirmed, and merged only once `gh pr checks`
reads CLEAN.

## Rules

1. **Branch-isolation, always.** Never commit to the default branch. Cut
   a feature branch first; the change lives and dies on it (constitution
   `branch-isolation`, NON-NEGOTIABLE).
2. **Stage by explicit path.** `git add <path>` for what belongs in the
   commit — never `git add -A`/`.` blindly. Verify with `git status` and
   `git diff --cached` before committing; a parallel agent's file must
   not leak in.
3. **Merge only on proven green.** After opening the PR, poll
   `gh pr checks <n>` until zero `pending` and zero failures, and
   `mergeStateStatus` is `CLEAN`. A merge on a pending check is a defect,
   not a shortcut.
4. **Force-push is scoped and lease-guarded.** Only after a deliberate
   rebase, only `--force-with-lease`, never on a shared branch.
5. **Verify the push landed.** Read the ref update line; don't assume.

## Process

1. Confirm the current branch. On the default branch → create the feature
   branch before touching anything.
2. Stage by path, review `git diff --cached`, commit with a conventional
   message.
3. Push and read the ref-update confirmation.
4. Open the PR; then poll `gh pr checks` to completion.
5. Merge only when checks are CLEAN; confirm the merge and sync the
   default branch.

## Proactive Triggers

Surface these WITHOUT being asked:

- a commit staged with `git add -A`/`.` → the explicit-path staging and the `git diff --cached` check that prevents a leak
- a merge requested while `gh pr checks` still shows `pending` → wait-for-green before the merge, with the check status quoted
- a `git push --force` without `--force-with-lease` on a branch others may hold → the lease-guarded form, or don't

## Output

```markdown
## GitHub Ops

**Change:** {what the branch carries}
**Branch:** {feature branch, off default}

### Steps (with evidence)
- staged: {paths} — `git diff --cached` reviewed
- pushed: {ref-update line}
- PR: #{n} — checks {CLEAN / list of pending→pass}

**Verdict:** {MERGED after green, confirmed / HELD — checks not yet CLEAN}
```
