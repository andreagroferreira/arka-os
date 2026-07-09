---
name: arka-update
description: >
  ArkaOS project sync orchestrator: detects what changed in core since the last sync and
  updates ecosystem skills, MCP configs, settings, and project descriptors via the hybrid
  Python engine plus AI subagent. TRIGGER: "/arka update", "sync projects", "atualiza os
  projetos", "update ArkaOS projects", or when SessionStart shows "[arka:update-available]";
  run AFTER `npx arkaos@latest update`. SKIP: updating the core itself -> `npx
  arkaos@latest update` in the terminal (this skill only syncs projects); day-to-day
  operational requests -> ops/operations.
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

1. **One-stop: npm refresh + engine (PR61 v2.78.0 orchestrator).**
   ```bash
   cd $ARKAOS_ROOT && ~/.arkaos/bin/arka-py -m core.sync.update_orchestrator --home ~/.arkaos --skills ~/.claude/skills --output json
   ```
   The orchestrator detects whether the running ArkaOS is behind npm
   latest. When stale, it shells out to `npx arkaos@latest update`
   first so the sync engine below reads fresh code; when current, it
   skips straight to the engine. Either way it runs the
   deterministic engine (manifest, discovery, MCP sync, settings
   sync, descriptors, content, agents) and writes
   `~/.arkaos/sync-state.json`.

   Probe is cached for 1 hour in `~/.arkaos/npm-latest.cache.json`
   to keep repeat runs cheap. Offline / `npx` missing → orchestrator
   silently skips the npm step and falls through to the engine.

   Fallback (no orchestrator): the underlying engine still runs the
   same way via `~/.arkaos/bin/arka-py -m core.sync.engine ...` for callers that
   don't need the version-drift gate.

2. **Phase 4 (intelligent, AI subagent):** After the engine completes, dispatch ONE subagent with the engine's JSON report + the feature registry (`core/sync/features/*.yaml`). The subagent injects/removes feature sections in each `~/.claude/skills/arka-{ecosystem}/SKILL.md` while preserving all custom content.

3. **Report:** Display the formatted summary returned by the engine,
   plus `installed_version_before` / `latest_version_seen` from the
   orchestrator so the operator sees what got refreshed.

## Error Handling (Summary)

- Python engine fails → report error, do not proceed to AI phase.
- AI subagent fails → deterministic sync already completed, report partial success.
- Individual project errors never stop other projects from syncing.

## References

- `references/sync-engine.md` — Python engine phases (manifest, discovery, MCP/settings/descriptor sync, state), feature registry format, key paths
- `references/workflows.md` — 2-step update flow, Phase 4 AI subagent instructions, report format, full error-handling table
