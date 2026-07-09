---
name: arka-checkpoint
description: >
  Inter-agent checkpoint pattern for long-running multi-agent work —
  fragments work into ~3-min sub-dispatches and emits proactive
  [arka:checkpoint] prompts so the user can inject context mid-task or
  abort cleanly (inter-agent-checkpoints SHOULD rule,
  core/orchestration/checkpoint.py). TRIGGER: "/arka checkpoint", any
  orchestration expected to block the user >30s — multi-reviewer Quality
  Gate, Forge explorer fan-out, research fan-out, sequential phase
  dispatches; "quero poder intervir a meio", "avisa-me entre passos",
  "let me add context mid-task". SKIP: work under 30 seconds or a single
  dispatch — run directly, fragmentation adds overhead; planning the work
  itself -> arka-forge (checkpoint paces the run, not the plan).
allowed-tools: [Read]
---

# /arka checkpoint — long-running work with user-in-the-loop

> Primitive layer for the inter-agent communication pattern decided
> in the 2026-05-13 Conclave Phase 5 brainstorm. Long-running work is
> fragmented; checkpoints are mandatory between sub-dispatches.

## When this applies

Any work item whose execution would block the user for **> 30 seconds**
(per `core.orchestration.checkpoint.should_checkpoint`). Typical cases:

- Multi-reviewer Quality Gate (Marta + Eduardo + Francisca parallel)
- Forge planning with 3-5 explorer subagents
- Research fan-out via `/arka research` (Perplexity + Exa + Context7 + ...)
- Multi-step implementation with sequential phase dispatches
- Anything where the user might want to inject "esqueci-me de mencionar X"

## The pattern

```
1. Orchestrator estimates total work (in seconds).
2. If > 30s, plan_fragmented_dispatches(task_name, sub_tasks)
   returns a CheckpointPlan with sub-dispatches of ~3 min each.
3. For each sub-dispatch:
     a. Emit [arka:checkpoint] Step N/T: next "<name>" ~Xs.
        Tens contexto a acrescentar antes? (Silêncio = procedo.)
     b. Run the sub-dispatch (Agent / Skill / etc.).
     c. Next turn: parse_user_injection(user_message) — if "abort",
        stop; if "context-injection", carry forward into next dispatch;
        otherwise treat as new-turn (the work plan may need replanning).
4. After all sub-dispatches: produce final synthesis + [arka:meta] tag.
```

## Conflict escalation (within a dispatch)

Per the brainstorm (Marta + Tomas):

- **Technical conflicts** between reviewers (e.g. Eduardo + Francisca
  disagree on a code-style call) → Marta resolves silently.
- **Strategic / taste / business-knowledge conflicts** → Marta surfaces
  the disagreement at the next checkpoint: *"Eduardo + Francisca
  discordam em X, eu inclino para A — qual o teu input?"*. The user
  decides; Marta records the decision for future similar cases.

## Output format example

```
[arka:checkpoint] Step 2/4: next dispatch "francisca-tech-review" — ~180s.
Tens contexto a acrescentar antes de eu arrancar? (Silêncio = procedo.)
  (Carry-forward: focus on backend SOLID + KISS specifically)
```

## What this does NOT do

- Does not implement real async execution. Claude Code Agent calls
  are synchronous; this skill defines the **pattern** the orchestrator
  follows by emitting checkpoint markers between agent calls.
- Does not block the user. The user is free to stay silent (proceed)
  or to send any message (parsed by `parse_user_injection`).
- Does not bypass the mandatory 13-phase flow. Checkpoints are
  emitted **inside** the per-todo loop of Phase 11.

## Cross-references

- Constitution rule: `inter-agent-checkpoints` (v2.32.0 PR10)
- Memory: [[project_arkaos_local_personal_agi]]
- Brainstorm: 2026-05-13 Conclave Phase 5
- Module: `core/orchestration/checkpoint.py`
