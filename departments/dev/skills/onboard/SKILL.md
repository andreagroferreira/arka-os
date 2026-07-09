---
name: arka-dev-onboard
description: >
  Onboard EXISTING projects into ARKA OS: auto-detects stack from
  composer.json/package.json/.env, analyzes architecture and git, applies MCP
  profiles, generates PROJECT.md and Obsidian pages, and manages ecosystems
  (groups of related projects like API + frontend). TRIGGER: "onboard",
  "regista o projeto", "add project", "import project", "ecosystem", "traz
  este projeto para o ArkaOS", "/dev onboard". SKIP: creating a NEW project
  from a template -> dev/scaffold (greenfield, not existing code);
  human-readable onboarding docs for developers -> dev/codebase-onboard.
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
