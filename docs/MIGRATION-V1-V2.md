# Migration Guide: ArkaOS v1 to v2

## What Changed

| | v1 | v2 |
|---|---|---|
| Core | Bash-only | Python + Node.js + Bash |
| Agents | 22 | 65 |
| Departments | 9 | 17 |
| Skills | ~30 | 244+ |
| Runtime | Claude Code only | Claude Code, Codex, Gemini, Cursor |
| Install | `git clone` | `npx arkaos install` |
| Install dir | `~/.claude/skills/arka-os` | `~/.arkaos` |
| Context | 5-layer Bash | 9-layer Python Synapse |
| Knowledge | Manual | Vector DB with semantic search |
| Dashboard | None | Nuxt 4 + FastAPI (8 pages) |

## How to Migrate

```bash
npx arkaos migrate
```

## What the Migration Does

1. **Detects** v1 at `~/.claude/skills/arka-os` or `~/.claude/skills/arkaos`
2. **Backs up** v1 to `~/.arkaos-v1-backup`
3. **Preserves** session digests and media files
4. **Installs** v2 at `~/.arkaos`
5. **Updates** Claude Code hooks to v2

Your v1 backup stays at `~/.arkaos-v1-backup` — delete it after confirming v2 works.

## Per-Project Setup

After global migration, initialize each project:

```bash
cd your-project
npx arkaos init
```

Creates `.arkaos.json` with auto-detected stack.

## Auto-Detection

The v2 hooks auto-detect v1 installations and show migration instructions. If you see a `[MIGRATION]` tag in your prompt context, run the migration command.

## Verify

```bash
npx arkaos doctor
```

All checks should pass after migration.
