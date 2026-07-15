---
name: ops/terminal-ops
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
allowed-tools: [Bash, Read, Grep, Glob]
metadata:
  origin: arkaos
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Terminal Ops — `/ops terminal-ops`

> **Agent:** Daniel (Ops Lead) | **Framework:** Evidence-flow G3, fail-fast, exit-code-as-truth

A command that prints a hopeful-looking line and a command that succeeded
are two different things, and the gap between them is where automation
quietly goes wrong. A migration that logged "applying…" and then threw, a
build whose warning scrolled past the real error, a script whose second
step ran against the failure of its first — each *looked* like progress.
This skill runs shell work so that the exit code, not the output, is the
verdict: capture it, check it, and stop the chain the moment it is
non-zero, rather than narrating success no one confirmed.

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
