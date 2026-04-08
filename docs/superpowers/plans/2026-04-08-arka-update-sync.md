# ArkaOS Update & Sync System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-powered `/arka update` command that detects version drift and synchronizes all project configurations (ecosystem skills, project descriptors, MCP configs, settings) via parallel subagents.

**Architecture:** Two components: (1) a bash hook addition to `user-prompt-submit-v2.sh` that compares `VERSION` with `~/.arkaos/sync-state.json` and injects a warning, (2) a new `/arka update` skill (`~/.claude/skills/arka-update/SKILL.md`) that orchestrates 4 subagents to sweep all project files. The skill reads core state (agents, MCPs, workflows), builds a change manifest, dispatches parallel subagents, writes sync state, and reports.

**Tech Stack:** Bash (hook), Markdown (SKILL.md skill definition), JSON (sync-state.json)

**Spec:** `docs/superpowers/specs/2026-04-08-arka-update-sync-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `config/hooks/user-prompt-submit-v2.sh` | Add version drift detection block |
| Modify | `installer/update.js` | Add sync-state reset after core update |
| Create | `~/.claude/skills/arka-update/SKILL.md` | The `/arka update` skill definition |
| Create | `tests/python/test_sync_state.py` | Tests for sync-state.json schema |
| Modify | `~/.claude/settings.json` | Register `/arka update` skill trigger |

---

### Task 1: Add Version Drift Detection to Synapse Hook

**Files:**
- Modify: `config/hooks/user-prompt-submit-v2.sh:19-20` (insert after V1 migration block)

- [ ] **Step 1: Write the version drift detection block**

Add this block after line 19 (after the V1 migration `done` statement), before the Performance Timing section:

```bash
# ─── Sync Version Detection ────────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
ARKAOS_VERSION_FILE="$HOME/.arkaos/.repo-path"

if [ -f "$ARKAOS_VERSION_FILE" ]; then
  _REPO_PATH=$(cat "$ARKAOS_VERSION_FILE")
  if [ -f "$_REPO_PATH/VERSION" ]; then
    _CURRENT_VERSION=$(cat "$_REPO_PATH/VERSION")
  elif [ -f "$_REPO_PATH/package.json" ]; then
    _CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$_REPO_PATH/package.json'))['version'])" 2>/dev/null || echo "")
  fi

  if [ -n "${_CURRENT_VERSION:-}" ]; then
    if [ -f "$SYNC_STATE" ]; then
      _SYNCED_VERSION=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
    else
      _SYNCED_VERSION="none"
    fi

    if [ "$_CURRENT_VERSION" != "$_SYNCED_VERSION" ]; then
      echo "{\"additionalContext\": \"[arka:update-available] ArkaOS v${_CURRENT_VERSION} installed (synced: ${_SYNCED_VERSION}). Run /arka update to sync all projects.\"}"
    fi
  fi
fi
```

- [ ] **Step 2: Verify the hook still produces valid JSON**

Run:
```bash
echo '{"userInput":"hello"}' | bash config/hooks/user-prompt-submit-v2.sh
```

Expected: Valid JSON output with `additionalContext` field. The `[arka:update-available]` message should appear because no `sync-state.json` exists yet.

- [ ] **Step 3: Verify hook exits normally when versions match**

Run:
```bash
mkdir -p ~/.arkaos
echo '{"version":"2.5.3","last_sync":"2026-04-08T00:00:00Z","projects_synced":0,"skills_synced":0,"errors":[]}' > ~/.arkaos/sync-state.json
echo '{"userInput":"hello"}' | bash config/hooks/user-prompt-submit-v2.sh
```

Expected: JSON output WITHOUT `[arka:update-available]` message (versions match).

- [ ] **Step 4: Clean up test state and commit**

```bash
rm -f ~/.arkaos/sync-state.json
git add config/hooks/user-prompt-submit-v2.sh
git commit -m "feat: add version drift detection to Synapse hook

Compares VERSION with sync-state.json on session start.
Injects [arka:update-available] message when versions differ."
```

---

### Task 2: Reset Sync State on Core Update

**Files:**
- Modify: `installer/update.js:130-136` (add sync-state reset in phase 6)

- [ ] **Step 1: Add sync-state version reset to update.js**

After line 134 (`manifest.updatedAt = new Date().toISOString();`), before `writeFileSync(manifestPath, ...)`, add:

```javascript
  // Reset sync state to trigger /arka update on next session
  const syncStatePath = join(installDir, "sync-state.json");
  const syncState = {
    version: "pending-sync",
    last_sync: null,
    projects_synced: 0,
    skills_synced: 0,
    errors: [],
    core_updated_to: VERSION,
    core_updated_at: new Date().toISOString()
  };
  writeFileSync(syncStatePath, JSON.stringify(syncState, null, 2));
  console.log("         ✓ Sync state reset (run /arka update to sync projects)");
```

- [ ] **Step 2: Update the post-update message to mention /arka update**

Replace the console.log block at lines 138-150 with:

```javascript
  console.log(`
  ╔══════════════════════════════════════════╗
  ║  ArkaOS updated to v${VERSION}              ║
  ╚══════════════════════════════════════════╝

  Your configuration is preserved:
    Language:  ${profile.language || "not set"}
    Market:    ${profile.market || "not set"}
    Projects:  ${profile.projectsDir || "not set"}
    Vault:     ${profile.vaultPath || "not set"}

  ⚠ Run /arka update in Claude Code to sync all projects.
  `);
```

- [ ] **Step 3: Commit**

```bash
git add installer/update.js
git commit -m "feat: reset sync-state on core update to trigger /arka update

After npx arkaos update, sync-state.json is set to pending-sync
so the Synapse hook prompts the user to run /arka update."
```

---

### Task 3: Create the `/arka update` Skill

**Files:**
- Create: `~/.claude/skills/arka-update/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/skills/arka-update
```

- [ ] **Step 2: Write the SKILL.md**

Create `~/.claude/skills/arka-update/SKILL.md` with the full skill definition:

```markdown
---
name: arka-update
description: >
  ArkaOS project sync orchestrator. Detects what changed in core since last sync
  and updates all ecosystem skills, project descriptors, MCP configs, and settings.
  Run when ArkaOS shows "[arka:update-available]" or manually anytime.
  Use when user says "/arka update", "sync projects", "update arka", or "actualizar projectos".
---

# ArkaOS Update — Project Sync Orchestrator

Synchronizes all project configurations with the current ArkaOS core.

## When To Run

- After `npx arkaos update` bumps the core version
- When the Synapse hook shows `[arka:update-available]`
- Manually: `/arka update` at any time to force a full sync

## Commands

| Command | Description |
|---------|-------------|
| `/arka update` | Full sync — detect changes, update everything, report |

## Orchestration Workflow

### Phase 1: Build Change Manifest

Read the current state of ArkaOS core and compare with last sync.

**Steps:**
1. Read `~/.arkaos/sync-state.json` to get `version` (last synced version)
   - If file missing or `version` is `"pending-sync"` or `"none"`: treat as first sync (full update)
2. Read `~/.arkaos/.repo-path` to locate the ArkaOS repo
3. From the repo, read:
   - `VERSION` file (current version)
   - `departments/*/agents/*.yaml` — all agent definitions (names, types, roles)
   - `~/.claude/skills/arka/mcps/registry.json` — current MCP server definitions
   - `departments/*/workflows/*.yaml` — current workflow definitions
4. If NOT first sync, run `git log <last_synced_version>..HEAD --oneline` in the repo to see what changed
5. Build a change manifest (in memory) summarizing:
   - Agents: added, removed, renamed, modified
   - MCPs: registry changes, added servers, removed servers
   - Departments: structural changes
   - Workflows: modified phases

**Output:** Announce the change manifest to the user:
```
ArkaOS Sync — v2.5.2 → v2.5.3
Changes detected:
  - 1 agent added (nano-banana)
  - 1 MCP removed (openai-image)
  - 1 MCP added (gemini-image)
  - 1 workflow modified (dev/feature.yaml)

Syncing all projects...
```

### Phase 2: Discover Projects

Find all projects that ArkaOS manages.

**Source 1: Ecosystem Registry**
- Read `~/.claude/skills/arka/knowledge/ecosystems.json`
- Extract all projects with their paths

**Source 2: Filesystem Scan**
- Read `~/.arkaos/profile.json` to get `projectsDir` paths
- Parse the projectsDir string to extract directories (may be comma-separated or description text)
- Common directories: `~/Herd/`, `~/Work/`, `~/AIProjects/`
- For each directory, list subdirectories
- A subdirectory is an ArkaOS project if it has ANY of: `.mcp.json`, `.claude/` directory, `CLAUDE.md`

**Source 3: Project Descriptors**
- List `~/.claude/skills/arka/projects/*.md` and `~/.claude/skills/arka/projects/*/PROJECT.md`
- Extract paths from YAML frontmatter

Deduplicate by path. Skip projects whose path does not exist on the filesystem.

**Output:** List of discovered projects with their ecosystem (if any) and stack.

### Phase 3: Dispatch Subagents

Launch 3 subagents in parallel using the Agent tool, then 1 sequential.

**IMPORTANT:** Each subagent receives:
1. The change manifest from Phase 1
2. Its specific file list from Phase 2
3. Clear instructions on what to update and what to preserve

#### Subagent 1: Skill Syncer

**Prompt template for the subagent:**
```
You are updating ArkaOS ecosystem skills to match the current core state.

CHANGE MANIFEST:
{paste the change manifest here}

CURRENT CORE STATE:
- Agent types available: {list all agent types from departments/*/agents/*.yaml}
- Workflow phases: {list the standard workflow phases}
- Department structure: {list departments}

FILES TO UPDATE:
{list all ~/.claude/skills/arka-*/SKILL.md paths}

FOR EACH SKILL FILE:
1. Read the current content
2. Update the "Squad Roles" table:
   - If any agent type in the table was renamed in the manifest, update it
   - If any agent type was removed, flag it with a comment
   - Do NOT change role names, specialties, or business context
3. Update the "Orchestration Workflow" section:
   - If workflow phases changed, update the phase list
   - Do NOT change ecosystem-specific workflow details
4. Update any hardcoded paths if they changed
5. Preserve ALL of:
   - Custom commands specific to the ecosystem
   - Business descriptions and client context
   - Architecture diagrams
   - Tech stack references
   - Obsidian output paths (unless the base path changed)
6. Write the updated file

REPORT: For each file, report: {path, status: updated|unchanged|error, changes: [list]}
```

#### Subagent 2: Descriptor Syncer

**Prompt template for the subagent:**
```
You are validating and updating ArkaOS project descriptors.

FILES TO UPDATE:
{list all ~/.claude/skills/arka/projects/*.md and */PROJECT.md paths}

FOR EACH DESCRIPTOR:
1. Read the current content
2. Check if the path in the YAML frontmatter exists on the filesystem
   - If path does not exist: add `status: archived` and a note
3. If path exists, read the project's package manager file:
   - composer.json → extract Laravel version, PHP version, key packages
   - package.json → extract framework (nuxt, next, react, vue), key deps
   - pyproject.toml → extract Python version, key deps
4. Compare detected stack with the `stack:` field in the descriptor
   - If different: update the stack field
5. Check git activity:
   - Run `git log --oneline -1 --format=%ci` in the project directory
   - If last commit > 30 days ago and status is "active": change to "paused"
   - If last commit < 7 days ago and status is "paused": change to "active"
6. Write the updated file

REPORT: For each file, report: {path, status: updated|unchanged|archived|error, changes: [list]}
```

#### Subagent 3: MCP Syncer

**Prompt template for the subagent:**
```
You are regenerating MCP configurations for all ArkaOS projects.

MCP REGISTRY (source of truth):
{paste full content of ~/.claude/skills/arka/mcps/registry.json}

STACK CONFIGS:
{paste content of ~/.claude/skills/arka/mcps/stacks/*.json if they exist}

PROJECTS TO UPDATE:
{list of projects with: path, stack (laravel/nuxt/react/python/etc), ecosystem}

FOR EACH PROJECT:
1. Read the current .mcp.json (if it exists)
2. Determine which MCPs this project should have:
   - ALWAYS include: arka-prompts, context7, obsidian, clickup, memory-bank, playwright, gh-grep
   - Laravel projects ADD: laravel-boost, serena, sentry
   - Nuxt/Vue projects ADD: nuxt-ui (if available in registry)
   - Shopify projects ADD: shopify-dev
   - Projects with PostgreSQL ADD: postgres
   - Projects with Supabase ADD: supabase
3. For the `serena` MCP: set `--project` arg to the project's actual path
4. For all MCPs: use the exact command/args/env from the registry
5. Preserve any MCP servers in the current .mcp.json that are NOT in the registry
   (these are project-specific custom MCPs the user added manually)
6. Write the updated .mcp.json

REPORT: For each project, report: {path, status: updated|unchanged|created|error, mcps_added: [], mcps_removed: []}
```

#### Subagent 4: Settings Syncer (runs AFTER Subagent 3 completes)

**Prompt template for the subagent:**
```
You are updating Claude Code settings for all ArkaOS projects.

PROJECTS TO UPDATE:
{list of projects with: path, their updated .mcp.json content from Subagent 3}

FOR EACH PROJECT:
1. Read the current .claude/settings.local.json (if it exists)
2. Read the project's .mcp.json to get the list of MCP server names
3. Update `enabledMcpjsonServers` to match the MCP servers in .mcp.json
4. Ensure `enableAllProjectMcpServers: true` is set
5. Preserve any custom `permissions` the user has configured
6. If .claude/settings.local.json does not exist, create it with:
   {
     "permissions": {
       "allow": ["Read", "Grep", "Glob", "WebFetch"]
     },
     "enableAllProjectMcpServers": true,
     "enabledMcpjsonServers": [<list from .mcp.json>]
   }
7. Write the updated file

REPORT: For each project, report: {path, status: updated|unchanged|created|error, changes: [list]}
```

### Phase 4: Write Sync State

After all subagents complete, write `~/.arkaos/sync-state.json`:

```json
{
  "version": "<current VERSION>",
  "last_sync": "<ISO 8601 timestamp>",
  "projects_synced": <count>,
  "skills_synced": <count>,
  "errors": [<any errors from subagent reports>]
}
```

### Phase 5: Report

Present a formatted summary:

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

## Error Handling

| Scenario | Action |
|----------|--------|
| Project path not found | Skip, report as warning, do not delete descriptor |
| No stack detectable | Use generic MCPs only (arka-prompts, context7, clickup, obsidian) |
| Ecosystem skill has manual customizations | Update ONLY structural sections, preserve everything else |
| First sync (no sync-state.json) | Full sync without diff, create sync-state.json |
| Version downgrade | Warn in report, sync to current version anyway |
| Subagent failure | Other subagents continue, report marks failure, sync-state records errors |

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.arkaos/sync-state.json` | Sync state tracker |
| `~/.arkaos/.repo-path` | Points to ArkaOS npm package |
| `~/.arkaos/profile.json` | User profile (projectsDir, vaultPath) |
| `~/.arkaos/install-manifest.json` | Installation metadata |
| `~/.claude/skills/arka/knowledge/ecosystems.json` | Project registry |
| `~/.claude/skills/arka/mcps/registry.json` | MCP server definitions |
| `~/.claude/skills/arka/projects/` | Project descriptors |
| `~/.claude/skills/arka-*/SKILL.md` | Ecosystem skills |
```

- [ ] **Step 3: Commit**

```bash
git add ~/.claude/skills/arka-update/SKILL.md
# Note: this file is outside the repo, so commit is not needed.
# Just verify it exists:
cat ~/.claude/skills/arka-update/SKILL.md | head -5
```

---

### Task 4: Register the Skill in settings.json

**Files:**
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Read current settings.json**

```bash
cat ~/.claude/settings.json
```

- [ ] **Step 2: Add the arka-update skill to the allowed tools list**

In the `settings.json`, find the `customInstructions` or skill registration section. Add a new entry for the `arka-update` skill following the same pattern as other `arka-*` skills.

The skill is registered by its directory name. Ensure it appears in the same section as other skills like `arka-dev`, `arka-brand`, etc.

- [ ] **Step 3: Verify the skill is recognized**

Open a new Claude Code session. Type `/arka update`. The skill should be loaded.

- [ ] **Step 4: Commit hook changes to the ArkaOS repo**

```bash
cd /Users/andreagroferreira/AIProjects/arka-os
git add config/hooks/user-prompt-submit-v2.sh installer/update.js
git commit -m "feat: add /arka update sync system — hook detection + installer integration

Version drift detection in Synapse hook compares VERSION with sync-state.json.
Installer resets sync-state after core update to trigger /arka update prompt."
```

---

### Task 5: Test End-to-End Flow

- [ ] **Step 1: Simulate a version bump**

```bash
cd /Users/andreagroferreira/AIProjects/arka-os
echo "2.5.4" > VERSION
```

- [ ] **Step 2: Verify hook detects the drift**

```bash
echo '{"userInput":"hello"}' | bash config/hooks/user-prompt-submit-v2.sh
```

Expected: Output contains `[arka:update-available] ArkaOS v2.5.4 installed (synced: none)`

- [ ] **Step 3: Run /arka update in Claude Code**

Open Claude Code and run `/arka update`. Verify:
- Change manifest is built and displayed
- Projects are discovered (ecosystem registry + filesystem scan)
- 4 subagents are dispatched (3 parallel + 1 sequential)
- All project files are updated
- sync-state.json is written with version "2.5.4"
- Report is displayed

- [ ] **Step 4: Verify hook no longer shows drift**

```bash
echo '{"userInput":"hello"}' | bash config/hooks/user-prompt-submit-v2.sh
```

Expected: Output does NOT contain `[arka:update-available]` (versions now match).

- [ ] **Step 5: Restore VERSION and commit test results**

```bash
echo "2.5.3" > VERSION
```

---

### Task 6: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add /arka update to the System Commands section**

In the CLAUDE.md, find the "Department Commands" or system commands area and add:

```markdown
## Sync System

| Command | Description |
|---------|-------------|
| `/arka update` | AI-powered sync — updates all ecosystem skills, project descriptors, MCP configs, and settings to match current ArkaOS core |

**Flow:** `npx arkaos update` → bumps core → hook detects drift → user runs `/arka update` → AI sweeps everything → report

**State file:** `~/.arkaos/sync-state.json`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add /arka update sync system to CLAUDE.md"
```
