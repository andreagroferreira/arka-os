# arka-update — workflows

Referenced from SKILL.md. Read only when needed.

## The 2-Step Update Flow

ArkaOS updates happen in two steps.

### Step 1: Core Update (terminal, outside Claude Code)

```bash
npx arkaos@latest update
```

Downloads the latest ArkaOS npm package and:
- Updates Python dependencies
- Copies new hook scripts (SessionStart, UserPromptSubmit, PostToolUse, PreCompact, CwdChanged)
- Updates the `/arka` skill and `arka-claude` CLI wrapper
- Resets sync state → triggers `[arka:update-available]` warning on next session

### Step 2: Project Sync (inside Claude Code)

```
/arka update
```

AI-powered sync that updates ecosystem skills, project descriptors, MCP configs, and Claude settings.

### When To Run

- After `npx arkaos@latest update` bumps the core version
- When the SessionStart hook shows `[arka:update-available]`
- Manually, any time, to force a full sync

## Orchestration

Every phase runs inside the Python engine. There is no AI phase: an agent
asked to edit these files cannot offer the guarantees the engine does, and
the instruction it used to carry — "otherwise remove the `## <section_title>`
section" — deleted customised sections outright.

### Phase 4 — Skill sync (`core/sync/skill_syncer.py`)

Scope is *user-owned* skills only: installed `arka-*` whose slug has no
`SKILL.md` in the core repo. Core skills ship from npm and are replaced by
`npx arkaos update`. Without a trustworthy core repo (sentinel slugs
present) nothing is in scope, so a broken checkout syncs nothing rather
than everything.

Per feature, per skill:

| Situation | What happens |
| --- | --- |
| Managed block present, content stale | rewritten from the registry |
| Managed block present, content current, stamp stale | stamp rewritten (`restamped`) |
| No block, unmarked section identical to canonical | adopted into a managed block |
| No block, unmarked section customised | **left untouched**, reported in `SKILL.md.arkaos-adopt.md` |
| No block, no section | block injected |
| Feature deprecated, block present | block removed |
| Feature deprecated, section customised | **left untouched**, reported |
| Markers unbalanced, duplicated or inverted | **file not touched at all**, reported |

Everything outside the markers belongs to the project and is never
rewritten. Proposals are deleted automatically once the divergence they
describe is gone.

### Report

Display the formatted report from the engine output:

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

| Scenario | Action |
|----------|--------|
| Python engine fails | Report error; do NOT proceed to AI phase |
| One skill fails to sync | Recorded against that skill; every other skill still syncs |
| Individual project error | Other projects continue; the failure is recorded in `sync-state.json` errors |
| Project path not found | Skip project, warn, do not delete its descriptor |
| No stack detectable | Use generic MCPs only (`arka-prompts`, `context7`, `clickup`, `obsidian`) |
| Ecosystem skill has manual customizations | Managed blocks are rewritten; customised sections are reported, never overwritten |
| First sync (no `sync-state.json` or version is `pending-sync` / `none`) | Full sync without diff, create `sync-state.json` |
| Version downgrade (sync-state version > current VERSION) | Warn in report, sync anyway |
| `.mcp.json` has MCPs not in registry | Preserve them (user-added, project-specific) |
| `.claude/settings.local.json` has custom permissions | Preserve them (user-configured) |
