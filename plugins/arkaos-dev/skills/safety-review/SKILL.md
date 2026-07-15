---
name: safety-review
description: >
  Audits a change or an automation for destructive, irreversible
  operations — bulk deletes, DROP/TRUNCATE, force pushes, mass emails,
  raw disk or filesystem writes — and checks each has a guard: a scope
  limit, a dry-run, a confirmation, a backup, a rollback. TRIGGER: "/dev
  safety-review", "is this safe to run", "destructive operation", "will
  this delete/overwrite", "review this migration/script/cron", "isto
  apaga alguma coisa?", "revê este script destrutivo", "posso correr isto
  em produção?"; run before shipping a migration, a bulk job, a cron, or
  an autonomous automation. SKIP: exploitable-vulnerability review ->
  dev/exploit-triage wins; general code review -> dev/code-review wins;
  the deploy/rollout mechanics themselves -> dev/deploy wins.
metadata:
  origin: arkaos
---

# Safety Review

> **Agent:** Bruno (Security Engineer) | **Framework:** Blast-radius analysis, reversibility, guard-before-execute

The dangerous change is rarely the one that fails — it is the one that
succeeds at the wrong scope. A migration that runs, a cleanup cron that
fires, a bulk update that commits: each does exactly what it was told, to
more rows or files or people than the author pictured. This lens finds
the destructive and irreversible operations in a change or an automation
and checks that every one is fenced — scoped, reversible, dry-runnable,
or gated behind a confirmation — before it can run unattended.

## What to flag

| Operation | The guard it needs |
|-----------|--------------------|
| **Bulk delete / update** (`DELETE`/`UPDATE` without a tight `WHERE`, `deleteMany`, `rm -rf`) | An explicit scope, a row-count check, and a backup or soft-delete |
| **Schema destruction** (`DROP`, `TRUNCATE`, a down-migration that loses data) | Reversibility or a snapshot; never irreversible without sign-off |
| **Force / history rewrite** (`git push --force`, `reset --hard`, `filter-branch`) | Branch scoping; never on a shared branch |
| **Mass outbound** (bulk email/notification/webhook) | A dry-run count, a rate limit, a test-recipient path |
| **Raw disk / filesystem** (`dd`, recursive writes, `chmod -R`) | Path scoping and a confirmation |
| **Unbounded loop / job** over production data | A limit, idempotency, and a resumable/rollback path |

## Process

1. Grep the change/automation for the destructive verbs — `DELETE`, `DROP`, `TRUNCATE`, `deleteMany`, `rm`, `--force`, `reset --hard`, bulk-send calls.
2. For each, determine the **blast radius**: what is the maximum it can affect if a parameter is wrong or empty (an empty `WHERE` deletes the table; a null filter matches everything)?
3. Check the guard is present and correct: scope, dry-run, confirmation, backup, rollback. A destructive op with no guard, or a guard that fails open, is a finding.
4. Rank by reversibility — an irreversible op with no backup is critical; a scoped, reversible one is clean.

## Proactive Triggers

Surface these WITHOUT being asked:

- a `DELETE`/`UPDATE` whose `WHERE` could evaluate to empty or all-rows → the full-table blast radius and the scope/guard it needs
- a down-migration or `DROP`/`TRUNCATE` with no snapshot → the irreversible data loss
- an automation that runs unattended (cron, agent, CI job) touching production data with no dry-run or rollback → the guard to add before it ships

## Output

```markdown
## Safety Review

**Scope:** {change / automation reviewed}
**Verdict:** {SAFE TO RUN / GUARDS REQUIRED}

### Destructive operations
- **{operation}** {file}:{line}
  - **Blast radius:** {worst case if a parameter is wrong/empty}
  - **Reversible?** {yes + how / no}
  - **Guard present?** {scope/dry-run/confirmation/backup — or missing}
  - **Fix:** {the guard to add before this runs}

### Safe
{operations already correctly fenced}
```
