---
name: arka-update
description: ArkaOS project sync orchestrator. Detects what changed in core since last sync and updates all ecosystem skills, MCPs, settings, and project descriptors.
---

# /arka update — Project Sync Engine

Hybrid sync engine: Python handles deterministic operations (MCPs, settings, descriptors), AI handles intelligent operations (ecosystem skill text updates).

## Usage

```
/arka update
```

## Commands

| Command | Description |
|---------|-------------|
| `/arka update` | Full sync — run engine, dispatch AI subagent for skills, write state, report |

## Orchestration (Summary)

1. **Phases 1–3 + 5 (deterministic, Python):** Run the engine:
   ```bash
   cd $ARKAOS_ROOT && python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills --output json
   ```
   Handles manifest, discovery, MCP sync, settings sync, descriptors, and writes `~/.arkaos/sync-state.json`.

2. **Phase 4 (intelligent, AI subagent):** After the engine completes, dispatch ONE subagent with the engine's JSON report + the feature registry (`core/sync/features/*.yaml`). The subagent injects/removes feature sections in each `~/.claude/skills/arka-{ecosystem}/SKILL.md` while preserving all custom content.

3. **Report:** Display the formatted summary returned by the engine.

## Error Handling (Summary)

- Python engine fails → report error, do not proceed to AI phase.
- AI subagent fails → deterministic sync already completed, report partial success.
- Individual project errors never stop other projects from syncing.

## References

- `references/sync-engine.md` — Python engine phases (manifest, discovery, MCP/settings/descriptor sync, state), feature registry format, key paths
- `references/workflows.md` — 2-step update flow, Phase 4 AI subagent instructions, report format, full error-handling table
