---
name: arka-dev-onboard
description: >
  Onboard existing projects into ARKA OS with automatic stack detection, codebase analysis,
  MCP configuration, and Obsidian documentation. Analyzes composer.json, package.json,
  .env files, directory structure to auto-detect framework, database, auth, payments, and
  architecture patterns. Generates PROJECT.md, applies MCP profiles, creates Obsidian project
  pages, and registers in ARKA OS — making any existing codebase "ready to work" with full
  context. Also manages project ecosystems (groups of related projects like API + frontend).
  Use when user says "onboard", "register project", "add project", "import project",
  "existing project", "ecosystem", or wants to bring an existing codebase into ARKA OS.
---

# Project Onboarding — ARKA OS Dev Department

Onboard existing projects into ARKA OS. Unlike `/dev scaffold` which creates NEW projects from templates, onboard analyzes EXISTING codebases and generates all the context, configuration, and documentation ARKA OS needs.

The goal: run one command, and the project is fully registered with stack detection, MCP configuration, Obsidian docs, and ecosystem assignment. No manual steps.

## Commands

| Command | Description |
|---------|-------------|
| `/dev onboard <path>` | Onboard an existing project |
| `/dev onboard <path> --ecosystem <name>` | Onboard and assign to an ecosystem |
| `/dev ecosystem list` | List all ecosystems and their projects |
| `/dev ecosystem create <name>` | Create a new ecosystem |
| `/dev ecosystem add <project> --to <ecosystem>` | Add existing project to ecosystem |

## Orchestration Overview

The onboard flow is a 12-step pipeline, split across two reference files:

**Detection phase** (stack-detection.md):
1. Validate path — resolve relative, check if already onboarded
2. Auto-detect stack — `detect-stack.py` returns framework, DB, auth, patterns, MCP profile
3. Architecture analysis — glob models/controllers/components to classify monolith/api/monorepo/SPA
4. Git analysis — remotes, branches, commits, contributors

**Configuration phase** (mcp-config.md):
5. Determine MCP profile — map framework to `laravel|nuxt|vue|react|nextjs|full-stack|base`
6. Ecosystem assignment — create/join/standalone
7. User confirmation — present analysis summary
8. Generate `PROJECT.md` in project root
9. Register in `$ARKA_OS/projects/<name>/`
10. Apply MCP profile — generate `.mcp.json` + `.claude/settings.local.json`
11. Create Obsidian docs — Home, Architecture, Projects MOC, Ecosystem MOC
12. Report — summary + next steps

The `ecosystem` subcommands (list/create/add) and error handling also live in mcp-config.md.

## References

Load on demand during execution:

- `references/stack-detection.md` — Steps 1-4: path validation, `detect-stack.py` output schema, manual detection fallbacks, architecture classification, git analysis commands
- `references/mcp-config.md` — Steps 5-12: MCP profile mapping, ecosystem assignment, PROJECT.md template, Obsidian page templates, ecosystem subcommand flows, error handling
