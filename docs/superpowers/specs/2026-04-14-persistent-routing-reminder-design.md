# Spec — Persistent Squad Routing Reminder

**Date:** 2026-04-14
**Reporter:** ClientAdvisory Oliveira
**Type:** bugfix / UX
**Tier:** Specialist (1-2 phases)

## Problem

Users observe that ArkaOS routes requests through department squads on the **first** turn (when `/arka` or a department skill is invoked), but subsequent turns drift back to generic assistant behavior. The squad identity fades even though the conversation continues.

Reported quote (pt-BR):
> "o claude está roteando para o arka só na primeira interação, depois no decorrer da conversa deixa de rotear e assume o controle"

## Root Cause

`squad-routing` and `arka-supremacy` ARE injected every turn via `UserPromptSubmit` → L0 Constitution. However they are buried inside a comma-separated list of 13 NON-NEGOTIABLE rules:

```
[Constitution] NON-NEGOTIABLE: branch-isolation, obsidian-output, ..., squad-routing, ..., arka-supremacy | ...
```

Low salience. The model reads it once on turn 1 (when skill content is fresh) but deprioritizes it on later turns when only the flat list is present. Skills are on-demand — `/arka` skill content is NOT re-loaded per turn.

## Solution

Add a dedicated, high-salience routing reminder tag as its own line in `additionalContext`, emitted by `UserPromptSubmit` on every turn:

```
[arka:route] Every response MUST route through a department squad. No generic assistant replies. Announce the squad before responding.
```

Short, imperative, unmissable. Separate from L0 flat list.

## Non-goals

- Do NOT auto-detect which department (that's Synapse L1/L5's job)
- Do NOT block responses (hook must remain non-blocking, exit 0)
- Do NOT re-load `/arka` skill content (token cost unjustified)

## Implementation

Edit `config/hooks/user-prompt-submit.sh`:

1. After `_OUT_CONTEXT` is assembled (line 197), prepend the routing tag.
2. Keep tag ≤150 chars to stay inside the 10s hook budget and avoid token bloat.
3. Tag is unconditional — cheap enough that no gating logic is needed.

## Verification

- Integration test: new pytest that invokes the hook with sample input and asserts `[arka:route]` is present in output JSON.
- Manual: start a fresh Claude Code session, have a 5-turn conversation, confirm squad announcement persists past turn 1.

## Rollback

Single file change. Revert commit if regression observed.
