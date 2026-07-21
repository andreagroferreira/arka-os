---
name: ops/hookify
description: >
  Compiles a repeated correction into a deterministic hook: identify
  the behavior that keeps being corrected by hand, express it as a
  machine-checkable predicate, and install it on the right ArkaOS hook
  surface (PreToolUse deny, Stop lint, UserPromptSubmit nudge) —
  warn-first with telemetry, hard only when the false-positive rate
  earns it. TRIGGER: "/ops hookify", "make this automatic", "torna isto
  automático", "estou farto de corrigir isto", "enforce this rule",
  "isto devia ser um hook"; the third manual correction of the same
  behavior. SKIP: capturing a reusable feature build -> arka-recipes
  wins; automating a business process -> ops/workflow-automate wins;
  writing an SOP for humans -> ops/sop-create wins.
allowed-tools: [Read, Grep, Glob, Bash, Write, Edit]
metadata:
  origin: arkaos
---

# Hookify — `/ops hookify`

> **Agent:** Daniel (Operations Lead) | **Framework:** Correction-to-predicate compilation, warn-first enforcement

A hook is a correction that stopped needing you. The third time the
same behavior gets fixed by hand — the commit message pattern, the file
that must never be edited directly, the command that needs a flag — the
correction has stopped being feedback and become a specification
nobody wrote down. This skill writes it down as executable policy.

## Step 1 — Extract the predicate

From the repeated correction, derive a predicate a machine can decide
WITHOUT judgment calls:

- **Good**: "Edit on `config/claude-agents/*.md` → deny (generated
  file; the YAML is the source)."
- **Not hookifiable**: "commit messages should be clearer" — no
  decidable predicate. Route vague quality intents to review skills,
  not hooks; a hook that needs judgment produces false positives that
  teach the operator to ignore every hook.

State the predicate as: *surface* (which tool calls / which moment),
*condition* (decidable test), *action* (deny / warn / inject context).

## Step 2 — Pick the surface

| Surface | When it fires | Right for | House examples |
|---|---|---|---|
| PreToolUse (`core/hooks/pre_tool_use.py`) | before a tool call | preventing an edit/command that must not happen | frontend gate, research gate |
| Stop (`core/hooks/stop.py`) | end of turn | measuring compliance, scoped lint over changed files | stop-lint, KB-cite check |
| UserPromptSubmit (`config/hooks/user-prompt-submit.sh`) | before the turn | nudges and context injection, never blocking | token hygiene checks |

Constraints that are not negotiable: hooks respect their timeout budget
(UserPromptSubmit 10s, PostToolUse 5s), never block on network, exit 0
on the non-blocking surfaces, and parse JSON with jq (python3
fallback). A hook that exceeds its budget degrades every turn to save
one correction — that trade is always refused.

## Step 3 — Warn first, harden on evidence

New enforcement ALWAYS lands warn-only with telemetry (house pattern:
the stop-lint and frontend-gate flips). The hook logs would-block
events to `~/.arkaos/telemetry/`; promotion to hard deny is a separate,
deliberate change gated on the observed false-positive rate — a gate
that fires wrongly even 1 turn in 50 gets disabled by hand and trains
contempt for the ones that fire rightly.

## Step 4 — Install with proof

1. Implement on the chosen surface, following that surface's existing
   pattern (read the sibling hooks first).
2. Reproduce the original correction scenario and show the hook
   catching it — a hook whose trigger was never exercised is a hope,
   not a control.
3. Show a benign scenario passing untouched (the false-positive probe).
4. Register the telemetry line and, if the hook grows a flag, document
   it where the surface's flags live.

## Output

```markdown
## Hookify Report

**Correction observed:** {what kept being fixed by hand, with instances}
**Predicate:** {surface} · {condition} · {action}
**Mode:** warn-only (telemetry: {file}) · hard-flip criterion: {rate}
**Proof:** trigger scenario caught ✓ · benign scenario untouched ✓
**Files:** {hook file, config, telemetry}
```
