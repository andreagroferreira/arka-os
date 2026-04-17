# Spec — Sync MCP Activation & Commands Syncer

**Date:** 2026-04-17
**Owner:** Paulo (Dev Lead), Daniel (Ops)
**Branch:** `fix/sync-mcp-activation-and-commands`
**Target release:** v2.18.0
**Status:** In progress

## Problem

After v2.17.5 sync, user-reported regressions:
1. MCPs listed in project `.mcp.json` not starting in Claude Code
2. Project-level commands not available
3. `mcp-decisions.cache.json` claims "cache lost"

Diagnostic confirmed:
- `mcp-decisions.cache.json`: 224 entries, 100% `deferred`, 0 `active`
- `engine.py` calls `optimize_all_mcps` with no `call_ai` callable → decider always returns `deferred`
- `settings_syncer.py` does not propagate MCP activation to `settings.local.json.enabledMcpjsonServers`
- No `commands_syncer.py` phase exists — projects never receive `.claude/commands/`
- `profile.json` has lowercase `herd`/`work` paths (macOS case-insensitive masks bug)

## Scope

Seven fixes, sequential, with visibility gates:

| # | Fix | File |
|---|---|---|
| 1 | Wire Haiku AiCaller in engine.py | `core/sync/engine.py`, new `core/sync/ai_caller.py` |
| 2 | Wipe stale mcp-decisions cache | `~/.arkaos/mcp-decisions.cache.json` (runtime) |
| 3 | Propagate active MCPs to `enabledMcpjsonServers` | `core/sync/settings_syncer.py` |
| 4 | Create `commands_syncer.py` + wire in engine | `core/sync/commands_syncer.py`, `core/sync/engine.py` |
| 5 | Fix profile.json path casing | `~/.arkaos/profile.json` (runtime) |
| 6 | Re-run `/arka update` and validate 3 projects | Manual |
| 7 | Add regression tests | `tests/python/sync/` |

## Out of scope

- Redesign of content_syncer or agent_provisioner
- Migration of project commands from v1 to v2
- Dashboard updates
- New MCP categories

## Technical decisions

### AiCaller (Fix #1)

- Model: `claude-haiku-4-5-20251001` (mechanical classification)
- Prompt: 2-line system prompt ("classify this MCP as `active` or `deferred` for a project with stack X"), user message = MCP name + description
- Fallback: `AIUnavailable` on network/key error → `deferred` (existing behavior)
- Cache: existing `mcp-decisions.cache.json` (sha256-keyed by stack+ecosystem+mcp)
- Budget: batch calls disabled; 1 call per unknown MCP; 30s timeout per call

### Settings syncer propagation (Fix #3)

Contract change:
- Input: `mcp_results: list[McpSyncResult]` (existing)
- Behavior: for each project, `enabledMcpjsonServers` = `final_mcp_list` (all MCPs in `.mcp.json`)
- Preserve: other keys in `settings.local.json` (permissions, env)
- Idempotent: unchanged status if list already matches

### Commands syncer (Fix #4)

Sources:
1. Global arka commands: all `~/.claude/skills/arka-*/SKILL.md` top entries → `/arka-*` shortcuts (symlink or text pointer)
2. Stack-specific templates: `config/standards/commands-templates/{stack}/*.md`

Target: `<project>/.claude/commands/`

Merge strategy:
- Write managed commands with frontmatter `arkaos-managed: true`
- Never overwrite user files (no `arkaos-managed` marker)
- Remove managed files whose template no longer exists

Minimum templates shipped in v2.18.0:
- `laravel/` — ships `test.md`, `migrate.md`, `artisan.md`
- `nuxt/` — ships `dev.md`, `build.md`, `lint.md`
- `react/` — ships `dev.md`, `test.md`, `build.md`
- `python/` — ships `test.md`, `lint.md`

**Update 2026-04-17**: Fix #4 (commands_syncer) was descoped during implementation.
Root cause analysis revealed that the perceived "missing project commands" was a
consequence of the `arka-prompts` MCP being deferred (Fix #1). Once the policy
rewrite activates `arka-prompts` on every stack, all department commands return
via the MCP prompt interface. A dedicated commands syncer is no longer required
for this release and is deferred to a future iteration.

## Acceptance criteria

1. After `/arka update`, `~/.arkaos/mcp-decisions.cache.json` has >0 `active` entries
2. For any project with stack=laravel: `.claude/settings.local.json.enabledMcpjsonServers` contains `laravel-boost`, `serena`, `postgres`, `context7`, `arka-prompts`, `obsidian`
3. Every synced project has `.claude/commands/` populated (at least `arka-status.md`)
4. `skills_synced` in sync-state reflects actual count (>0) or renamed to `commands_synced`
5. `profile.json` uses correct path casing (`/Users/andreagroferreira/Herd`, `/Users/andreagroferreira/Work`)
6. Regression tests pass: `test_mcps_enabled_matches_mcp_json`, `test_commands_dir_populated`, `test_ai_decider_called`
7. Full `pytest tests/python/sync/` green (0 failures, 0 errors)

## Test plan

```bash
# Unit
pytest tests/python/sync/test_settings_syncer.py -v
pytest tests/python/sync/test_commands_syncer.py -v
pytest tests/python/sync/test_ai_caller.py -v

# Integration
pytest tests/python/sync/test_engine_integration.py -v

# Manual validation (Fix #6)
python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills
# Expect: ~200+ active MCPs decisions, commands deployed to Edp/burrowhub/crm-rockport
```

## Quality Gate

Mandatory before merge. Model: Opus.
- Marta (CQO) orchestrates
- Eduardo reviews all docstrings/comments/user-facing strings
- Francisca reviews code quality, test coverage ≥80%, SOLID/Clean Code compliance

## Release pipeline

1. Bump VERSION, package.json, pyproject.toml → 2.18.0
2. Conventional commit: `feat(sync): MCP activation + commands syncer + AI decider (fixes #42)`
3. Push to master after review
4. `gh release create v2.18.0`
5. `npm publish --access public`
6. `npm view arkaos version` must show 2.18.0
