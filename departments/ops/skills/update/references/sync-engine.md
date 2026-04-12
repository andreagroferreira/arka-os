# arka-update — sync engine

Referenced from SKILL.md. Read only when needed.

## Python Engine Invocation

Run the sync engine from the ArkaOS repo root:

```bash
cd $ARKAOS_ROOT && python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills --output json
```

The engine handles deterministic operations and returns a JSON report.

## Engine Phases

### Phase 1 — Manifest
- Reads `~/.arkaos/sync-state.json` (last synced version)
- Compares against current `VERSION` from the repo
- Loads feature registry from `core/sync/features/*.yaml` (or `~/.arkaos/config/sync/features/*.yaml`)
- Builds change manifest (agents, MCPs, workflows, features added/removed/modified)

### Phase 2 — Discovery
Combines three sources to find all ArkaOS-managed projects:
1. **Ecosystem registry:** `~/.claude/skills/arka/knowledge/ecosystems.json`
2. **Filesystem scan:** projectsDir from `~/.arkaos/profile.json` (e.g. `~/Herd/`, `~/Work/`, `~/AIProjects/`). A subdir counts as an ArkaOS project if it has any of: `.mcp.json`, `.claude/`, `CLAUDE.md`.
3. **Descriptors:** `~/.claude/skills/arka/projects/*.md` and `~/.claude/skills/arka/projects/*/PROJECT.md`

Deduplicate by absolute path. Skip projects whose path does not exist.

### Phase 3a — MCP Sync
For each project: regenerate `.mcp.json` based on the registry + detected stack.

Base MCPs (all projects): `arka-prompts`, `context7`, `obsidian`, `clickup`, `memory-bank`, `playwright`, `gh-grep`.

Stack additions:
- Laravel: `laravel-boost`, `serena`, `sentry`
- Nuxt/Vue: nuxt-specific MCPs from registry
- Shopify: `shopify-dev`
- PostgreSQL / Supabase: matching MCP if in registry

Rules:
- `serena` MCP: update `--project` arg to the project's absolute path
- All MCPs: copy exact command/args/env from registry; resolve `~`/`${HOME}` to real path
- **Preserve** project-specific MCPs not in the registry (user-added)

### Phase 3b — Settings Sync
Align `.claude/settings.local.json` with the updated `.mcp.json`:
- `enabledMcpjsonServers` matches the final MCP server list
- `enableAllProjectMcpServers: true`
- **Preserve** any custom `permissions` the user has configured
- If the file does not exist, create it with permissions `["Read","Grep","Glob","WebFetch"]` plus the MCP list

### Phase 3c — Descriptors
For each descriptor:
- If `path:` no longer exists: `status: archived` + note "Path not found on filesystem"
- Detect stack from `composer.json` / `package.json` / `pyproject.toml` and update `stack:`
- Git activity: last commit > 30 days ago + active → paused; < 7 days + paused → active
- Validate `ecosystem:` matches an existing `~/.claude/skills/arka-*/`

### Phase 5 — State
Writes `~/.arkaos/sync-state.json`:
```json
{
  "version": "<current VERSION>",
  "last_sync": "<ISO 8601>",
  "projects_synced": <count>,
  "skills_synced": <count>,
  "errors": [<messages>]
}
```
Returns JSON report for downstream consumption.

## Feature Registry

YAML files under `core/sync/features/*.yaml` (or `~/.arkaos/config/sync/features/*.yaml`). Each feature has:
- `detection_pattern` — regex/string searched in ecosystem SKILL.md to decide if the feature is already present
- `content` — the section to inject if missing
- `deprecated_in` — if set, the matching section is removed

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.arkaos/sync-state.json` | Sync state (version, timestamp, counts, errors) |
| `~/.arkaos/.repo-path` | Points to the ArkaOS npm package directory |
| `~/.arkaos/profile.json` | User profile (language, market, projectsDir, vaultPath) |
| `~/.arkaos/install-manifest.json` | Installation metadata |
| `~/.claude/skills/arka/knowledge/ecosystems.json` | Ecosystem registry |
| `~/.claude/skills/arka/mcps/registry.json` | MCP server definitions (source of truth) |
| `~/.claude/skills/arka/mcps/stacks/*.json` | Stack-specific package/MCP configs |
| `~/.claude/skills/arka/projects/` | Project descriptor files |
| `~/.claude/skills/arka-*/SKILL.md` | Ecosystem skill definitions |
