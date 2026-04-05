# Migration Guide: ArkaOS v1 → v2

## What Changed

| Aspect | v1 | v2 |
|--------|-----|-----|
| Name | ARKA OS | ArkaOS |
| Install | `bash install.sh` | `npx arkaos install` |
| Tech | Bash-only | Python + Node.js + Bash |
| Agents | 22 (DISC only) | 62 (DISC + Enneagram + Big Five + MBTI) |
| Departments | 9 | 16 |
| Commands | ~135 | 216 |
| Workflows | Hardcoded in SKILL.md | YAML-defined, declarative |
| Runtime | Claude Code only | Claude Code + Codex + Gemini + Cursor |
| Config | JSON | YAML (agents, workflows, constitution) |
| Install dir | `~/.claude/skills/arka/` | `~/.arkaos/` |
| CLI | `arka` | `arkaos` |

## Migration Steps

### 1. Install v2

```bash
npx arkaos install
```

This installs v2 alongside v1. They don't conflict.

### 2. Verify Installation

```bash
npx arkaos doctor
```

All checks should pass.

### 3. Update Projects

v1 project files (`PROJECT.md`, `.project-path`) work unchanged in v2.
No project migration needed.

### 4. Agent Memory

v1 agent memory at `~/.claude/agent-memory/arka-*/MEMORY.md` is preserved.
v2 agents read from the same location.

### 5. Obsidian Vault

No changes. v2 uses the same Obsidian paths as v1.

### 6. Remove v1 (Optional)

Once comfortable with v2:

```bash
# Remove v1 skills
rm -rf ~/.claude/skills/arka

# Remove v1 hooks (v2 installer already overwrites them)
# Check ~/.claude/settings.json — v2 hooks should be active
```

## New Departments (Not in v1)

| Department | Prefix | What's New |
|-----------|--------|-----------|
| SaaS | `/saas` | Validation, metrics, PLG, pricing |
| Landing Pages | `/landing` | Funnels, offers, copy, affiliate |
| Content | `/content` | Viral, hooks, scripts, repurposing |
| Community | `/community` | Groups, membership, engagement |
| Sales | `/sales` | Pipeline, proposals, SPIN, negotiation |
| Leadership | `/lead` | Team health, hiring, OKRs, culture |
| Project Management | `/pm` | Scrum, Kanban, Shape Up, discovery |

## New Features (Not in v1)

- **The Conclave** — Personal AI advisory board (20 advisors, DNA profiling)
- **Living Specs** — Specs that track implementation and record deltas
- **Multi-Runtime** — Works with Codex CLI, Gemini CLI, Cursor
- **Background Tasks** — Async job queue for KB downloads, analysis
- **Squad Framework** — Matrix org with ad-hoc cross-department squads

## Command Changes

Most v1 commands work unchanged. New prefix commands:

```
/saas, /landing, /content, /community, /sales, /lead, /pm, /org
```

The `/do` orchestrator now routes to all 16 departments.
