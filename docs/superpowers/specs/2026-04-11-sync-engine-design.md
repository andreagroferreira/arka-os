# ArkaOS Sync Engine — Design Specification

> Hybrid sync engine that makes `/arka update` actually work.

## Problem

`/arka update` is documented but not implemented. The SKILL.md describes a 5-phase AI-orchestrated sync with 4 subagents, but no executable code exists. Result: after `npx arkaos update`, ecosystem skills, project MCPs, settings, and descriptors are never updated. Projects like ClientCommerce stay frozen in time — missing Forge integration, spec-driven gate, updated workflow tiers, and any future feature added to core.

## Solution

A hybrid sync engine where Python handles all deterministic operations (MCPs, settings, descriptors, stack detection) and AI handles operations requiring judgment (updating ecosystem skill text with new features).

## Architecture

```
/arka update
    │
    ├── Phase 1: Change Manifest (Python)
    │   Read sync-state, compare versions, generate feature diff
    │
    ├── Phase 2: Project Discovery (Python)
    │   3 sources: ecosystems.json + filesystem scan + project descriptors
    │
    ├── Phase 3: Deterministic Sync (Python)
    │   ├── 3a. MCP Syncer — registry.json → .mcp.json per project
    │   ├── 3b. Settings Syncer — .mcp.json → settings.local.json
    │   └── 3c. Descriptor Syncer — stack detection, status auto-demotion
    │
    ├── Phase 4: Intelligent Sync (AI subagent)
    │   └── Skill Syncer — feature registry → ecosystem SKILL.md updates
    │
    └── Phase 5: Write State + Report (Python)
        sync-state.json + formatted report
```

### Code Location

```
core/sync/
├── __init__.py
├── engine.py            # Orchestrator — runs phases 1-3, 5
├── manifest.py          # Phase 1: change manifest builder
├── discovery.py         # Phase 2: project discovery from 3 sources
├── mcp_syncer.py        # Phase 3a: .mcp.json updates
├── settings_syncer.py   # Phase 3b: settings.local.json updates
├── descriptor_syncer.py # Phase 3c: project descriptor updates
├── reporter.py          # Phase 5: formatted output + state write
└── features/            # Feature registry (propagated by npx update)
    ├── forge.yaml
    ├── spec-gate.yaml
    ├── workflow-tiers.yaml
    └── quality-gate.yaml
```

### Invocation

The `/arka update` SKILL.md calls the Python engine for deterministic phases, then dispatches 1 AI subagent for skill sync:

```bash
# Phase 1-3 + 5 (deterministic)
python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills --output json

# Phase 4 (AI) — subagent reads engine output + feature registry
```

The engine outputs a JSON report that the SKILL.md uses for the final formatted display and that the AI subagent uses to know which skills need updating.

## Phase 1: Change Manifest

### Input
- `~/.arkaos/sync-state.json` — last synced version
- `$ARKAOS_ROOT/VERSION` — current version
- `$ARKAOS_ROOT` path from `~/.arkaos/.repo-path`

### Logic
1. Read sync-state. If missing or `version: "pending-sync"` → treat as first sync (full update).
2. Read VERSION for current version.
3. If incremental sync: run `git log v{old}..v{new} --oneline` in ArkaOS repo to detect changes.
4. Parse conventional commits to extract: features added, fixes, breaking changes.
5. Read feature registry (`core/sync/features/*.yaml`) to build list of all propagatable features with their `added_in` versions.

### Output
```python
@dataclass
class ChangeManifest:
    previous_version: str        # "2.14.0" or "pending-sync"
    current_version: str         # "2.15.0"
    is_first_sync: bool
    features: list[FeatureSpec]  # All features from registry
    new_features: list[str]      # Features added since last sync
    deprecated_features: list[str]
```

## Phase 2: Project Discovery

### Sources

**Source 1: Ecosystem registry**
- Read `~/.claude/skills/arka/knowledge/ecosystems.json`
- Extract all projects with paths from ecosystem entries

**Source 2: Filesystem scan**
- Read `~/.arkaos/profile.json` for `projectsDir` paths (e.g., `~/Herd`, `~/Work`, `~/AIProjects`)
- List subdirectories in each path
- A subdirectory is a project if it has: `.mcp.json` OR `.claude/` directory OR `CLAUDE.md`

**Source 3: Project descriptors**
- List `~/.claude/skills/arka/projects/*.md` and `~/.claude/skills/arka/projects/*/PROJECT.md`
- Extract `path:` from YAML frontmatter

### Deduplication
By absolute resolved path. Skip paths that don't exist on filesystem.

### Stack Detection
For each discovered project, detect stack by reading package manager files:
- `composer.json` → Laravel (check `require.laravel/framework`)
- `package.json` → check for `nuxt`, `next`, `vue`, `react` in dependencies
- `pyproject.toml` → Python
- `Shopify` theme files → Shopify

### Output
```python
@dataclass
class Project:
    path: str                    # Absolute path
    name: str                    # Directory name
    ecosystem: str | None        # "client_commerce", "client_retail", etc.
    stack: list[str]             # ["laravel", "php"]
    descriptor_path: str | None  # Path to project descriptor .md
    has_mcp_json: bool
    has_settings: bool
```

## Phase 3a: MCP Syncer

### Input
- MCP registry: `~/.claude/skills/arka/mcps/registry.json`
- List of projects with detected stacks

### Logic per project

1. Read `registry.json` — each MCP has a `category` field: `base`, `laravel`, `nuxt`, `react`, `ecommerce`, `comms`, `brand`.
2. Determine which MCPs the project should have:
   - **All projects:** MCPs with `category: "base"` (arka-prompts, context7, obsidian, clickup, memory-bank, playwright, gh-grep)
   - **Laravel projects:** ADD MCPs with `category: "laravel"` (laravel-boost, serena, sentry)
   - **Nuxt/Vue projects:** ADD MCPs with `category: "nuxt"`
   - **React/Next.js projects:** ADD MCPs with `category: "react"`
   - **Shopify/E-commerce projects:** ADD MCPs with `category: "ecommerce"`
3. Read current `.mcp.json` (if exists).
4. Merge:
   - **Add** MCPs from registry that should be present but aren't
   - **Remove** MCPs that exist in current `.mcp.json` AND exist in registry with a different category that doesn't match project stack (i.e., MCP was deprecated or recategorized)
   - **Preserve** MCPs in current `.mcp.json` that are NOT in registry at all (user-added, project-specific)
   - **Update** command/args/env for MCPs that exist in both, using registry as source of truth
5. For `serena` MCP: set `--project` argument to the project's absolute path.
6. Replace `{home}` and `~` placeholders in registry values with actual `$HOME`.
7. Write updated `.mcp.json` with 2-space indent.

### Output per project
```python
@dataclass
class McpSyncResult:
    path: str
    status: str          # "updated" | "unchanged" | "created" | "error"
    mcps_added: list[str]
    mcps_removed: list[str]
    mcps_updated: list[str]
    mcps_preserved: list[str]  # user-added, not in registry
    final_mcp_list: list[str]  # all MCP server names after sync
    error: str | None
```

## Phase 3b: Settings Syncer

### Input
- Projects with their `final_mcp_list` from Phase 3a

### Logic per project

1. Read current `.claude/settings.local.json` (if exists).
2. Update `enabledMcpjsonServers` array to match `final_mcp_list`.
3. Ensure `enableAllProjectMcpServers: true` is set.
4. **Preserve** all existing `permissions` entries (Bash rules, MCP method allowlists).
5. If file doesn't exist, create `.claude/` directory and write:
   ```json
   {
     "permissions": {
       "allow": ["Read", "Grep", "Glob", "WebFetch"]
     },
     "enableAllProjectMcpServers": true,
     "enabledMcpjsonServers": ["<list from final_mcp_list>"]
   }
   ```
6. Write with 2-space indent JSON.

### Output per project
```python
@dataclass
class SettingsSyncResult:
    path: str
    status: str          # "updated" | "unchanged" | "created" | "error"
    servers_added: list[str]
    servers_removed: list[str]
    error: str | None
```

## Phase 3c: Descriptor Syncer

### Input
- Discovered projects with detected stacks
- Project descriptors from `~/.claude/skills/arka/projects/`

### Logic per descriptor

1. **Path validation:** Check if `path:` exists on filesystem.
   - If not → set `status: archived` in frontmatter
   - Do NOT delete the descriptor file

2. **Stack detection:** Compare detected stack with `stack:` field in frontmatter.
   - If different → update `stack:` field
   - Only update if detection is confident (package manager file found)

3. **Activity check:** Run `git log -1 --format=%ci` in project path.
   - If >30 days since last commit AND `status: active` → change to `status: paused`
   - If <7 days since last commit AND `status: paused` → change to `status: active`
   - If git fails (not a repo) → skip activity check

4. **Ecosystem validation:** Check if `ecosystem:` field references an existing skill (`~/.claude/skills/arka-{ecosystem}/`).
   - If skill doesn't exist → log warning (don't change the field)

5. **Write changes:** Update YAML frontmatter in-place, preserving markdown body.

### Output per descriptor
```python
@dataclass
class DescriptorSyncResult:
    path: str
    status: str       # "updated" | "unchanged" | "archived" | "error"
    changes: list[str]  # ["status: active → paused", "stack updated"]
    error: str | None
```

## Phase 4: Intelligent Sync (AI Subagent)

### Feature Registry

Each propagatable feature is a YAML file in `core/sync/features/`:

```yaml
# core/sync/features/forge.yaml
name: forge-integration
added_in: "2.14.0"
mandatory: true
section_title: "Forge Integration"
detection_pattern: "arka-forge"
deprecated_in: null
content: |
  ## Forge Integration

  Complex requests (complexity score >= 5) are automatically routed to
  The Forge for multi-agent planning before execution.

  - Phase 0.5: Forge analysis (after spec creation, before squad planning)
  - Complexity assessment: automatic via Synapse L8 (ForgeContextLayer)
  - Manual invocation: `/forge` command
  - Handoff: Forge outputs structured plan → squad executes phases
```

```yaml
# core/sync/features/spec-gate.yaml
name: spec-driven-gate
added_in: "2.13.0"
mandatory: true
section_title: "Spec-Driven Development"
detection_pattern: "arka-spec"
deprecated_in: null
content: |
  ## Spec-Driven Development

  Phase 0 of all workflows. No implementation begins without a validated spec.

  - Invocation: automatic before any feature/fix work
  - Gate: spec must be approved before planning phase starts
  - Storage: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - Review: user approval required on written spec
```

```yaml
# core/sync/features/workflow-tiers.yaml
name: workflow-tiers
added_in: "2.12.0"
mandatory: true
section_title: "Workflow Tiers"
detection_pattern: "Enterprise.*phase|Focused.*phase|Specialist.*phase"
deprecated_in: null
content: |
  ## Workflow Tiers

  Three workflow tiers based on task complexity:

  | Tier | Phases | When |
  |------|--------|------|
  | Enterprise | 7-10 phases | Complex features, multi-file changes |
  | Focused | 3-5 phases | Medium tasks, single-domain changes |
  | Specialist | 1-2 phases | Simple tasks, quick fixes |

  Tier selection is automatic based on complexity assessment.
  Quality Gate phase is mandatory on ALL tiers.
```

```yaml
# core/sync/features/quality-gate.yaml
name: quality-gate
added_in: "2.10.0"
mandatory: true
section_title: "Quality Gate"
detection_pattern: "Marta.*CQO|Quality Gate"
deprecated_in: null
content: |
  ## Quality Gate

  Mandatory on every workflow. Nothing ships without approval.

  - **Marta (CQO):** Orchestrates review, absolute veto power
  - **Eduardo (Copy Director):** Reviews all text output
  - **Francisca (Tech Director):** Reviews all code and technical output
  - Verdict: APPROVED or REJECTED (binary, no partial)
```

### Subagent Behavior

The AI subagent receives:
1. The change manifest (from Phase 1)
2. The feature registry files (all `.yaml` files from `core/sync/features/`)
3. The list of ecosystem skills to check (`~/.claude/skills/arka-{ecosystem}/SKILL.md`)

For each ecosystem skill:
1. Read the current SKILL.md
2. For each feature in the registry where `deprecated_in` is null:
   - Search SKILL.md for `detection_pattern`
   - If NOT found → inject `content` after the last existing feature section, or after the "Commands" table if no feature sections exist yet (before "Orchestration Workflows" section)
3. For each feature where `deprecated_in` is set and <= current version:
   - Search SKILL.md for the section
   - If found → remove it
4. **Preserve:** All custom content — commands, architecture descriptions, tech stack details, business descriptions, Obsidian paths, YAML frontmatter

### What the subagent does NOT touch
- Command tables (custom per ecosystem)
- Squad roles (custom per ecosystem)
- Architecture descriptions
- Tech stack details
- Business context paragraphs
- Obsidian output paths
- YAML frontmatter (name, description)

## Phase 5: Write State + Report

### Sync State
After all phases complete, write `~/.arkaos/sync-state.json`:

```json
{
  "version": "2.15.0",
  "last_sync": "2026-04-11T22:30:00.000Z",
  "projects_synced": 22,
  "skills_synced": 6,
  "errors": []
}
```

### Report Format
```
═══════════════════════════════════════════════════════
  ArkaOS Sync Complete — v2.14.0 → v2.15.0
═══════════════════════════════════════════════════════

  MCPs:         22 projects synced (8 updated, 14 unchanged)
  Settings:     22 projects synced (8 updated, 14 unchanged)
  Descriptors:  22 synced (2 paused, 1 archived, 19 unchanged)
  Skills:       6 ecosystems synced (4 updated, 2 unchanged)

  Key changes:
  • Forge integration added to: client_commerce, client_retail, client_media, client_fashion
  • Spec-driven gate added to: client_commerce, client_retail
  • New MCP "gemini-image" added to 8 Laravel projects
  • Deprecated MCP "openai-image" removed from 3 projects
  • 2 projects auto-paused (no commits >30d): lora-tester, purz-comfyui

  Errors: 0
═══════════════════════════════════════════════════════
```

## SKILL.md Update

The existing `/arka update` SKILL.md will be rewritten to:

1. Call `python -m core.sync.engine` for Phases 1-3 + 5
2. Parse the JSON output
3. If skills need updating → dispatch 1 AI subagent with feature registry + skill list
4. Display the formatted report

This replaces the current 4-subagent design with 1 Python process + 1 subagent.

## Installer Integration

The `npx arkaos update` (installer/update.js) Phase 6 (Skills and agents) must also copy:
- `core/sync/features/*.yaml` → `~/.arkaos/config/sync/features/`
- `core/sync/` Python modules → already installed via editable pip install

No other installer changes needed — the Python modules are already available via the editable install.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Project path doesn't exist | Skip MCP/settings sync, mark descriptor as archived |
| No stack detectable | Use base MCPs only (no stack-specific additions) |
| `.mcp.json` parse error | Skip project, log error, continue with others |
| `settings.local.json` parse error | Skip project, log error, continue with others |
| Git not available in project | Skip activity check for descriptor |
| Feature registry file malformed | Skip that feature, log warning |
| AI subagent fails | Deterministic sync still completes, report partial failure |
| First sync (no prior state) | Full sync — treat all features as new, all projects as needing update |
| Version downgrade | Warn in report, sync anyway |
| Custom MCPs not in registry | Preserve them (user-added) |
| Custom permissions in settings | Preserve them (user-configured) |

## Testing Strategy

### Unit Tests (Python, pytest)
- `test_manifest.py` — version comparison, git log parsing, feature registry loading
- `test_discovery.py` — project discovery from each source, deduplication, stack detection
- `test_mcp_syncer.py` — MCP merge logic (add, remove, preserve, update), placeholder replacement, serena path
- `test_settings_syncer.py` — enabledMcpjsonServers alignment, permission preservation, file creation
- `test_descriptor_syncer.py` — status transitions, stack updates, frontmatter parsing
- `test_reporter.py` — state file writing, report formatting
- `test_engine.py` — full orchestration, phase ordering

### Integration Tests
- End-to-end sync with mock filesystem (temp directories with sample projects)
- Verify `.mcp.json` and `settings.local.json` are correctly written
- Verify descriptor frontmatter is correctly updated

### Test Fixtures
- Sample `registry.json` with 5-6 MCPs across categories
- Sample project directories with `composer.json`, `package.json`
- Sample ecosystem SKILL.md files missing various features
- Sample `sync-state.json` at different states (pending, old version, current)

## Dependencies

- `pyyaml` — already installed (YAML parsing for features, descriptors)
- `pydantic` — already installed (data models)
- `json` — stdlib (MCP and settings file handling)
- `subprocess` — stdlib (git commands for activity check and manifest)
- `pathlib` — stdlib (path operations)
- No new dependencies required.

## Migration

For users with existing projects:
1. First run after upgrade: `is_first_sync = True` → full sync of everything
2. All existing `.mcp.json` files are merged (not overwritten) — custom MCPs preserved
3. All existing `settings.local.json` permissions are preserved
4. All existing ecosystem skills get missing features injected without touching custom content
