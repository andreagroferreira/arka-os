# MCP Infrastructure Commit — Design Spec

**Date:** 2026-04-11
**Status:** Approved
**Scope:** Commit existing MCP infrastructure to repo so installer can deploy it

## Problem

The MCP management system (registry, profiles, scripts, arka-prompts server) exists only in the local install at `~/.claude/skills/arka/mcps/`. It was never committed to the repository. Fresh installations silently skip MCP setup because the installer tries to copy from `mcps/` in the repo — which doesn't exist.

This affects 30K users: skills `arka-mcp`, `arka-scaffold`, and `arka-onboard` reference scripts that don't exist in new installations.

## Solution

Copy the existing, working MCP infrastructure from `~/.claude/skills/arka/` to the repo at `mcps/`, fix 3 hardcoded personal paths, and update the installer to deploy the directory.

## File Structure

```
mcps/
├── registry.json              — 30+ MCP definitions ({home} templated)
├── profiles/                  — 10 profile bundles
│   ├── base.json
│   ├── laravel.json
│   ├── nuxt.json
│   ├── vue.json
│   ├── react.json
│   ├── nextjs.json
│   ├── ecommerce.json
│   ├── full-stack.json
│   ├── comms.json
│   ├── brand.json
│   └── social.json
├── stacks/                    — Package lists per framework
│   ├── laravel-packages.json
│   └── react-packages.json
├── scripts/
│   └── apply-mcps.sh          — Generates .mcp.json for projects
└── arka-prompts/              — MCP server source
    ├── server.py
    ├── commands.py
    ├── pyproject.toml
    └── .gitignore              — Excludes .venv/, __pycache__/
```

Excluded from commit: `.venv/`, `uv.lock`, `__pycache__/`.

## Security Fixes

Three hardcoded paths in `registry.json` replaced with `{home}` placeholder:

| Original | Replacement |
|----------|-------------|
| `/Users/andreagroferreira/.claude/skills/arka/mcp-server` | `{home}/.claude/skills/arka/mcp-server` |
| `/Users/andreagroferreira/Documents/Personal` | `{home}/Documents/Personal` |
| `/Users/andreagroferreira/memory-bank` | `{home}/memory-bank` |

## Script Fix

`apply-mcps.sh` — extend existing `{cwd}` sed replacement to also resolve `{home}`:

```bash
sed "s|{cwd}|$PROJECT_DIR|g; s|{home}|$HOME|g"
```

## Installer Changes

`installer/index.js` and `installer/update.js` — add step to copy `mcps/` directory to `~/.claude/skills/arka/mcps/` during install/update. The arka-prompts server goes to `~/.claude/skills/arka/mcp-server/`.

## Skills

No changes needed. `$ARKA_OS/mcps/scripts/apply-mcps.sh` already resolves correctly because `$ARKA_OS` points to `~/.claude/skills/arka` where files are deployed.

## Validation

1. `registry.json` contains no personal paths (grep verification)
2. `apply-mcps.sh` resolves `{home}` correctly
3. Installer copies `mcps/` to destination
4. End-to-end: `apply-mcps.sh laravel --project /tmp/test` generates valid `.mcp.json`
5. Full pytest suite (2002 tests) passes
6. Quality Gate (Eduardo + Francisca)
