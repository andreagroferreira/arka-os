---
name: terminal-ops
description: >
  Runs shell operations the evidence-first way — every command's exit
  code and real output are captured and checked before anything is
  reported as done, and a non-zero exit stops the chain instead of being
  narrated over. TRIGGER: "/ops terminal-ops", "run this safely",
  "execute and verify", "did this command actually work", "corre isto e
  confirma", "verifica o exit code", "isto correu mesmo?"; use when a task
  hangs on a sequence of shell commands whose success must be proven, not
  assumed. SKIP: git/GitHub-specific flows (branch, PR, merge-on-green) ->
  ops/github-ops wins; a CI/CD deployment pipeline -> dev/deploy wins;
  documenting the procedure instead of running it -> ops/sop-create wins.
metadata:
  origin: arkaos
---

# Terminal Ops

> **Agent:** Daniel (Ops Lead) | **Framework:** Evidence-flow G3, fail-fast, exit-code-as-truth

The deploy script exits 0. One line up sits `Error: connection refused`
— but a wrapper swallowed the real status and handed back the echo, so
the pipeline read green and shipped a half-applied migration. No one
lied; the output simply never got checked against the exit code, and the
exit code never got checked at all. Terminal-ops runs shell work under a
single rule: the status is the verdict and the output is only a hint
toward it. Anything that matters has its exit code captured and read
against a success signal named in advance, and a non-zero exit halts the
sequence rather than scrolling past.

## Principles

1. **Exit code is the truth, output is a hint.** `echo $?` (or the tool's
   own status) after anything that matters. A zero exit with an empty
   result is still a result to inspect; a non-zero exit is a stop.
2. **Chain on success, never on hope.** Sequence with `&&` or an explicit
   status check between steps, so step 2 cannot run on step 1's failure.
3. **Capture, then read.** Redirect output you need to judge (`2>&1`),
   read it, and quote the line that proves the claim — never report "done"
   from memory of what the command *should* do.
4. **Least surprise on destructive verbs.** Before `rm`/`mv`/`>`
   overwrites, confirm scope (what it matches) — hand off to
   `ops/github-ops` for history rewrites and `dev/db-design` for schema.

## Process

1. State the goal and the **success signal** in advance — the exact exit
   code, file, or output that will prove it.
2. Run the command, capturing status and the output you need to judge.
3. Read the result against the success signal. Match → proceed. Mismatch
   → stop, surface the real error line, do not continue the chain.
4. Report with the evidence: the command, its exit code, and the line
   that confirms it.

## Proactive Triggers

Surface these WITHOUT being asked:

- a multi-step sequence where a later step assumes an earlier one passed → the status check to insert between them
- a command whose success was reported from its output text, not its exit code → the `$?`/status check that actually proves it
- a destructive command (`rm -rf`, `>`, `truncate`) with an unbounded or unchecked target → the scope confirmation before it runs

## Output

```markdown
## Terminal Ops

**Goal:** {what the sequence had to achieve}
**Success signal:** {the exit code / file / output line that proves it}

### Executed
- `{command}` → exit {code} — {the line that confirms or refutes}

**Verdict:** {DONE, proven by evidence above / STOPPED at step N — real error}
```
