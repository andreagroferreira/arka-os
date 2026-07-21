---
name: workspace-audit
description: >
  Sweeps every repository in the workspace for the entropy that
  accumulates between projects: dirty working trees, unpushed commits,
  orphaned branches, forgotten stashes, repos without remotes, and
  secrets sitting outside .gitignore — then reports per repo with the
  one command that clears each finding. TRIGGER: "/ops workspace-audit",
  "audit my workspace", "varre os meus projetos", "que repos estão
  sujos?", "o que tenho por commitar?", periodic hygiene, and after any
  tool that mass-edits files across projects. SKIP: branch/merge
  discipline within one change -> ops/github-ops wins; ArkaOS install
  health -> the doctor (npx arkaos doctor) wins; one project's
  dependency risk -> dev/dependency-audit wins.
metadata:
  origin: arkaos
---

# Workspace Audit

> **Agent:** Daniel (Operations Lead) | **Framework:** Read-only sweep, finding-to-command mapping

Workspaces do not break; they silt. One repo keeps a dirty tree from a
config sync, another holds a commit that never got pushed, a third has
a stash nobody remembers making — each harmless alone, none announced,
all invisible until the day one of them eats an afternoon or, worse, a
piece of work. The sweep exists because no single project's tooling
looks ACROSS projects.

## Sweep

For every git repository under the workspace roots (honoring the
operator's project layout — e.g. `~/Herd` for Laravel, `~/Work` for
Node/Nuxt/Python — plus any explicitly given path):

| # | Check | Finding when |
|---|---|---|
| 1 | Working tree | `git status --porcelain` non-empty |
| 2 | Unpushed work | commits ahead of upstream, or branch with no upstream |
| 3 | Stashes | `git stash list` non-empty (each stash is work in limbo) |
| 4 | Orphaned branches | local branches fully merged into the default branch, or with no activity beyond an age threshold |
| 5 | No remote | repository with zero remotes (single-disk work) |
| 6 | Secrets exposure | `.env*` / key files present AND not matched by .gitignore |
| 7 | Detached HEAD | repo parked on no branch |

**The audit is strictly read-only.** It runs inspection commands only
and never fixes anything itself — a sweep that mutates sixty repos to
"help" is a bigger incident than anything it would find. Every finding
ships with the exact command that clears it; running them is the
operator's call, repo by repo.

## Triage

Findings are ranked by loss potential, not by count:

1. **Work at risk** — dirty trees, unpushed commits, stashes, detached
   HEADs, no-remote repos: things that can LOSE work.
2. **Exposure** — secrets outside .gitignore: things that can LEAK.
3. **Clutter** — orphaned branches: things that cost attention only.

A workspace with 40 clutter findings and one unpushed repo leads with
the unpushed repo.

## Output

```markdown
## Workspace Audit — {date}

**Roots:** {paths} · **Repos scanned:** {n} · **Clean:** {n}

### Work at risk ({n})
| Repo | Finding | Clear with |
|---|---|---|
| {path} | {e.g. 3 commits unpushed on feat/x} | `git push origin feat/x` |

### Exposure ({n})
| Repo | Finding | Clear with |

### Clutter ({n})
{collapsed list: repo — branches}

**Verdict:** {the one thing to do first, and why it outranks the rest}
```

Repeated audits should trend toward boring: a finding that reappears
every sweep is a process gap — route it to ops/hookify or an SOP
instead of clearing it by hand a fourth time.
