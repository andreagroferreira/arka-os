# Spec — Mandatory Subagent Context Handoff

**Date:** 2026-04-14
**Reporter:** Marlon Oliveira (via Andre)
**Type:** feature / API change
**Tier:** Focused (3-5 phases) — breaking API change

## Problem

`HandoffArtifact.context_summary` (core/runtime/subagent.py:45) and `SubagentDispatcher.create_handoff` (line 122) both default `context_summary=""`. Orchestrators frequently dispatch subagents without populating it — subagents start fresh with only a task description, losing:

- Prior decisions made in the conversation
- Files already read/inspected by the orchestrator
- Findings from sibling subagents
- User constraints expressed earlier

User-visible symptom: "scopes a meio perdem contexto que já devia ter do passado".

## Root Cause

The API makes context passing optional and silent. Nothing warns the orchestrator when it skips the handoff summary. Combined with Synapse being reactive (per-prompt), subagents get only the 8-layer context for their *own* prompt — none of the orchestrator's accumulated state.

## Solution

**Two-layer enforcement:**

### Layer 1 — API: make context_summary mandatory, fail-loud when empty

```python
def create_handoff(
    self,
    agent: Agent,
    task_description: str,
    context_summary: str,        # positional, no default
    relevant_files: list[str] | None = None,
    ...
) -> HandoffArtifact:
    if not context_summary.strip():
        raise ValueError(
            "context_summary is required. Pass a compacted summary of "
            "prior decisions, findings, and user constraints. Use "
            "ContextCompactor.build() if you need help."
        )
```

### Layer 2 — Helper: `ContextCompactor` to build summaries automatically

New class `core/runtime/context_compactor.py`:

```python
class ContextCompactor:
    """Builds compact context summaries for subagent handoff.

    Compacts: last N user messages, recent decisions,
    files touched, active workflow phase, KB chunks.
    """
    def build(
        self,
        conversation_turns: list[Turn],
        max_tokens: int = 600,
    ) -> str:
        ...
```

Target: ~600-token summary (~5× the current ~379-token artifact, but worth it).

## Non-goals

- Do not auto-inject full conversation history (token bloat, privacy)
- Do not break nested dispatches — enforce at one level only

## Migration

All existing callers of `create_handoff` must pass `context_summary`. Grep shows (to be verified):

- `core/workflow/*` workflow executors
- `departments/*/workflows/*.yaml` dispatch hooks
- Tests in `tests/python/runtime/`

Phased:
1. Add `ContextCompactor` + tests (non-breaking)
2. Update all internal callers to build and pass summary
3. Flip `context_summary` to required positional — emit `DeprecationWarning` for one minor version before `ValueError`

## Verification

- Unit: `ContextCompactor.build()` produces valid summary under token budget
- Unit: `create_handoff()` raises on empty `context_summary`
- Integration: dispatch flow verifies subagent receives non-empty context
- Manual: multi-turn conversation with subagent dispatch — subagent demonstrably references prior decisions

## Rollout

Ship behind `ARKAOS_STRICT_HANDOFF=1` env flag for one minor version, then default-on in the next major bump.

## Open Questions

1. Should `ContextCompactor` use an LLM pass to compress, or rule-based only? (LLM = better quality, latency cost)
2. Should workflow engine auto-inject `context_summary` for declarative YAML dispatches?
3. How does this interact with `SubagentResult.to_summary()` when a subagent spawns... nothing — policy is no nesting.

**Requires user approval before implementation.**
