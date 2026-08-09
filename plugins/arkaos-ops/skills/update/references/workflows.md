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

## Hybrid Orchestration

The Python engine (see `sync-engine.md`) runs every deterministic phase: manifest, discovery, MCP sync, settings sync, descriptors, content sync (CLAUDE.md managed block, rules, hooks, constitution excerpt), agent provisioning, and state. Phase 4 runs as ONE AI subagent to handle intelligent ecosystem-skill text updates.

### Phase 4 — Intelligent Sync (AI Subagent)

After the Python engine completes, dispatch ONE subagent.

**Subagent input:**
- The JSON report from the engine (list of ecosystems that exist)
- The feature registry files from `core/sync/features/*.yaml` (or `~/.arkaos/config/sync/features/*.yaml`)

**Subagent task — for each `~/.claude/skills/arka-{ecosystem}/SKILL.md`:**
1. Read the SKILL.md.
2. For each feature YAML where `deprecated_in` is null:
   - Apply the `detection_pattern` regex to the SKILL.md text. It matches the `arka:feature:<name>` marker, the bare `## <section_title>` heading, or a unique historical keyword — a customized section without markers still counts as present and MUST NOT be duplicated.
   - If NOT found: inject through `core.sync.feature_injector.inject_feature`, never by hand, at the offset after the last existing feature section — or after the "Commands" table if no feature sections exist (before "Orchestration Workflows").
   - The injector REFUSES any offset sitting inside an unterminated `<!--` and returns an `InjectionRefusal` instead of new text. Record it in the report's `injection_refusals` and leave the file exactly as it was; the host keeps missing that section until someone closes the comment. Issue #509: a hand-picked offset once landed four marker blocks between a `<!--` on line 20 and its `-->` on line 74, so the first marker's own `-->` closed the WRONG comment and the outer comment's tail rendered as garbage above the commands table.
3. For each feature where `deprecated_in` is set:
   - Remove the `<!-- arka:feature:<name>:start -->` … `:end -->` block ONLY when a single, well-formed marker pair exists.
   - **Never delete an unmarked `## <section_title>` section.** Without markers there is no way to tell ArkaOS's own text from the project's, and a section the operator customized looks identical to one they did not. Leave it in place and report it instead. `~/.claude/skills/` is not a git repository — a wrong deletion there is unrecoverable.
   - If the markers are unbalanced, duplicated or inverted, do not edit the file at all; report the fault.
4. PRESERVE all custom content: commands, architecture, tech stack, business descriptions, ecosystem-specific workflow details.

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
| AI subagent fails | Deterministic sync already completed; report partial success |
| Individual project error | Other projects continue; the failure is recorded in `sync-state.json` errors |
| Project path not found | Skip project, warn, do not delete its descriptor |
| No stack detectable | Use generic MCPs only (`arka-prompts`, `context7`, `clickup`, `obsidian`) |
| Ecosystem skill has manual customizations | Update only structural sections; preserve all custom content |
| First sync (no `sync-state.json` or version is `pending-sync` / `none`) | Full sync without diff, create `sync-state.json` |
| Version downgrade (sync-state version > current VERSION) | Warn in report, sync anyway |
| `.mcp.json` has MCPs not in registry | Preserve them (user-added, project-specific) |
| `.claude/settings.local.json` has custom permissions | Preserve them (user-configured) |
