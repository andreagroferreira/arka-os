# ArkaOS Update & Sync System

**Date:** 2026-04-08
**Status:** Approved
**Version:** 1.0

## Problem

ArkaOS has 3 layers of per-project configuration — ecosystem skills (8 SKILL.md), project descriptors (20+ .md), MCP configs (26+ .mcp.json) — and none of them synchronize when the core updates. Projects configured with V1 or earlier V2 versions drift silently: different agent types, missing workflows, outdated MCP servers. Behavior becomes inconsistent across projects, and the user must repeatedly insist on squad routing and workflow compliance.

## Solution

AI-powered sync system with two components:

1. **Version detection hook** — Synapse hook compares `VERSION` with `sync-state.json` on every session start. If different, injects a message: "Run /arka update to sync all projects."
2. **`/arka update` skill** — Orchestrator agent builds a change manifest, dispatches parallel subagents to update all project configurations, writes sync state, and reports results.

## Architecture

```
npx arkaos update              → Updates core files (Node.js installer, already exists)
                               → Bumps VERSION

Open Claude Code               → Synapse hook detects version mismatch
                               → "[arka:update-available] Run /arka update"

/arka update                   → AI orchestrator:
                                  Phase 1: Build change manifest (diff core vs last sync)
                                  Phase 2: Dispatch 3 parallel + 1 sequential subagent
                                  Phase 3: Write sync-state.json
                                  Phase 4: Report
```

## Component 1: Version Detection Hook

### Changes to `user-prompt-submit.sh`

After existing context injection, add version comparison:

```bash
ARKAOS_VERSION=$(cat "$REPO_PATH/VERSION")
SYNC_STATE="$HOME/.arkaos/sync-state.json"

if [ -f "$SYNC_STATE" ]; then
  SYNCED_VERSION=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])")
else
  SYNCED_VERSION="none"
fi

if [ "$ARKAOS_VERSION" != "$SYNCED_VERSION" ]; then
  echo "[arka:update-available] ArkaOS $ARKAOS_VERSION available (synced: $SYNCED_VERSION). Run /arka update to sync all projects."
fi
```

### `sync-state.json` (new file)

**Location:** `~/.arkaos/sync-state.json`
**Created by:** `/arka update` at the end of execution
**Read by:** Synapse hook at session start

```json
{
  "version": "2.5.3",
  "last_sync": "2026-04-08T16:52:00Z",
  "projects_synced": 26,
  "skills_synced": 8,
  "errors": []
}
```

## Component 2: `/arka update` Skill

### New skill: `arka-update`

**Location:** `~/.claude/skills/arka-update/SKILL.md`
**Trigger:** User writes `/arka update` or hook suggests it

### Phase 1: Change Manifest

Before touching any file, the orchestrator builds a semantic diff between current core and last sync:

```yaml
version_from: "2.5.2"
version_to: "2.5.3"
changes:
  agents:
    added: ["nano-banana"]
    removed: []
    renamed: {}
    modified: ["paulo"]
  departments:
    added: []
    removed: []
    modified: ["dev"]
  mcps:
    registry_changed: true
    added: ["gemini-image"]
    removed: ["openai-image"]
  workflows:
    modified: ["dev/feature.yaml"]
  agent_types:
    renamed: {}
```

The manifest is built by comparing:
- `departments/*/agents/*.yaml` — agent names, types, roles
- `~/.claude/skills/arka/mcps/registry.json` — MCP servers
- `departments/*/workflows/*.yaml` — workflow phases
- Git diff between `sync-state.version` and current `VERSION`

### Phase 2: Subagent Dispatch

3 parallel + 1 sequential subagent, each receives the change manifest + its file list:

```
Phase 2:
├─ Parallel:
│  ├─ Subagent 1: Skill Syncer (8 ecosystem SKILL.md)
│  ├─ Subagent 2: Descriptor Syncer (20+ project .md)
│  └─ Subagent 3: MCP Syncer (26+ .mcp.json)
│
└─ Sequential (after MCP Syncer):
   └─ Subagent 4: Settings Syncer (26+ settings.local.json)
```

### Subagent 1 — Skill Syncer

**Scope:** `~/.claude/skills/arka-*/SKILL.md` (8 ecosystem skills)

**Updates:**
- Agent types — semantic find-replace if core renamed agent types (e.g., `senior-dev` → `backend-engineer`)
- Workflow phases — insert/modify orchestration workflow sections if core added/changed phases
- Squad roles — update agent type references in squad role tables
- Paths and references — registry path, project paths, Obsidian output paths

**Preserves:**
- Custom ecosystem commands (e.g., `/clubefashion migration plan`)
- Business descriptions and client context
- Stack and architecture specific to the project
- Client-specific constraints

### Subagent 2 — Descriptor Syncer

**Scope:** `~/.claude/skills/arka/projects/*.md` (20+ project descriptors)

**Updates:**
- Validates paths — does the project at `path:` still exist on filesystem?
- Stack detection — reads `composer.json` / `package.json` and updates `stack:` if changed
- Status — if project has no commits in 30+ days, marks as `paused`
- Ecosystem link — verifies `ecosystem:` field corresponds to an existing skill

### Subagent 3 — MCP Syncer

**Scope:** `<project>/.mcp.json` (26+ projects)

**Updates:**
- Regenerates from registry — reads `~/.claude/skills/arka/mcps/registry.json` + `stacks/<stack>.json`
- Stack-aware — Laravel projects get `laravel-boost`, Nuxt get `nuxt-mcp`, etc.
- Serena path — updates `--project` to correct path
- Removes deprecated MCPs — if a server was removed from registry, removes from projects
- Adds new MCPs — if a server was added to registry and is compatible with the stack, adds it

### Subagent 4 — Settings Syncer

**Scope:** `<project>/.claude/settings.local.json` (26+ projects)

**Updates:**
- `enabledMcpjsonServers` — aligns with MCPs that exist in the updated `.mcp.json`
- Permissions — ensures baseline permissions are consistent

**Dependency:** Runs AFTER MCP Syncer completes (not parallel).

### Phase 3: Write Sync State

Writes `~/.arkaos/sync-state.json` with current version, timestamp, counts, and any errors.

### Phase 4: Report

```
═══════════════════════════════════════════
  ArkaOS Sync Complete — v2.5.2 → v2.5.3
═══════════════════════════════════════════

  Skills:       8 synced (3 updated, 5 unchanged)
  Descriptors: 22 synced (5 updated, 17 unchanged)
  MCP Configs: 26 synced (26 updated — new provider added)
  Settings:    26 synced (0 changed)

  Changes applied:
  - Agent "nano-banana" added to dev department
  - OpenAI removed from image routing across all MCPs
  - Google Gemini added as image provider

  Errors: 0
  Sync state saved to ~/.arkaos/sync-state.json
═══════════════════════════════════════════
```

## Project Discovery

### Two sources combined:

**Source 1: Ecosystem Registry** (already exists)
- `~/.claude/skills/arka/knowledge/ecosystems.json` lists projects per ecosystem
- Covers 22+ projects across 8 ecosystems

**Source 2: Filesystem Scan** (new)
- Scans known directories from `profile.json`: `~/Herd/`, `~/Work/`, `~/AIProjects/`
- Detection criteria: has `.mcp.json` OR `.claude/` directory OR `CLAUDE.md`
- Catches standalone projects not in any ecosystem

No permanent inventory file — rebuilt on each `/arka update` run.

## Error Handling

| Scenario | Action |
|----------|--------|
| Project path not found | Skip, report as `path not found`, do not delete descriptor |
| No stack detectable | Keep `.mcp.json` with generic MCPs only (context7, arka-prompts, clickup, obsidian) |
| Ecosystem skill has manual customizations | Update ONLY structural sections (agent types, workflow, squad table), preserve everything else |
| First sync (no sync-state.json) | Full sync without diff, create sync-state.json |
| Version downgrade (sync-state > VERSION) | Warn in report, sync to current version anyway |
| Subagent failure | Other subagents continue, report marks failure, sync-state records errors for next retry |

## Files Created/Modified

### New files:
- `~/.arkaos/sync-state.json` — sync state tracker
- `~/.claude/skills/arka-update/SKILL.md` — the update skill

### Modified files:
- `~/.arkaos/config/hooks/user-prompt-submit-v2.sh` — version detection block added
- Up to 80+ project files updated per sync run (8 skills + 20+ descriptors + 26+ MCPs + 26+ settings)
