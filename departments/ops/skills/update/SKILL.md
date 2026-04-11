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

## How It Works

### Phase 1-3 + 5: Deterministic Sync (Python)

Run the sync engine:
```bash
cd $ARKAOS_ROOT && python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills --output json
```

The engine:
1. **Phase 1 (Manifest):** Reads sync-state.json, compares versions, loads feature registry
2. **Phase 2 (Discovery):** Finds all projects from 3 sources (descriptors, filesystem, ecosystems)
3. **Phase 3a (MCP Sync):** Updates .mcp.json per project based on registry + stack
4. **Phase 3b (Settings Sync):** Aligns settings.local.json with .mcp.json
5. **Phase 3c (Descriptors):** Auto-pause inactive, archive missing, update stacks
6. **Phase 5 (State):** Writes sync-state.json and returns JSON report

### Phase 4: Intelligent Sync (AI Subagent)

After the Python engine completes, dispatch ONE subagent to update ecosystem skills:

**Subagent input:**
- The JSON report from the engine (which ecosystems exist)
- The feature registry files from `core/sync/features/*.yaml` (or `~/.arkaos/config/sync/features/*.yaml`)

**Subagent task:**
For each ecosystem skill (`~/.claude/skills/arka-{ecosystem}/SKILL.md`):
1. Read the SKILL.md
2. For each feature YAML where `deprecated_in` is null:
   - Search SKILL.md for `detection_pattern`
   - If NOT found → inject `content` after the last existing feature section, or after the "Commands" table if no feature sections exist yet (before "Orchestration Workflows" section)
3. For each feature where `deprecated_in` is set:
   - Search for and remove the section
4. PRESERVE all custom content: commands, architecture, tech stack, business descriptions

### Report

Display the formatted report from the engine output. The engine's text output format:
```
═══════════════════════════════════════════════════════
  ArkaOS Sync Complete — v2.14.0 → v2.15.0
═══════════════════════════════════════════════════════
  MCPs:         22 synced (8 updated, 14 unchanged)
  Settings:     22 synced (8 updated, 14 unchanged)
  Descriptors:  5 synced (1 updated, 4 unchanged)
  Skills:       3 ecosystems synced (2 updated, 1 unchanged)
  ...
```

## Error Handling

- If Python engine fails: report the error, do not proceed to AI phase
- If AI subagent fails: deterministic sync already completed, report partial success
- Individual project errors don't stop other projects from syncing
