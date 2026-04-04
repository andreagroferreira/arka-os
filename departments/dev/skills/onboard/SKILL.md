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

## Workflow: /dev onboard <path>

### Step 1: Validate Path

```python
python3 "$ARKA_OS/../arka-onboard/scripts/detect-stack.py" "<path>" --json
```

If the path doesn't exist, resolve relative to `$HOME` or common project directories (`~/Herd/`, `~/Projects/`, `~/Code/`).

Check if already onboarded: look for `projects/<name>/PROJECT.md` in `$ARKA_OS`.

### Step 2: Auto-Detect Stack

Run the bundled detection script:

```bash
python3 "$(dirname "$0")/scripts/detect-stack.py" "<resolved-path>" --json
```

This returns a JSON report with:
- **Framework** — Laravel, Nuxt, Vue, React, Next.js, Django, FastAPI, etc.
- **Language** — PHP, TypeScript, Python, etc.
- **Stack** — full list of detected technologies
- **Database** — PostgreSQL, MySQL, SQLite, Supabase
- **Cache/Queue** — Redis, Horizon
- **Auth** — Sanctum, Passport, NextAuth, Supabase Auth
- **Payments** — Stripe, Paddle
- **CSS** — Tailwind, Sass, Nuxt UI, shadcn/ui
- **Testing** — Pest, PHPUnit, Vitest, Jest, Playwright
- **Architecture** — monolith, api-only, monorepo, frontend-spa
- **Patterns** — Services, Repositories, Actions, DTOs
- **Conventions** — TypeScript, ESLint, Prettier, PHPStan, Docker
- **Metrics** — models, controllers, migrations, components, pages, tests
- **MCP Profile** — recommended profile (laravel/nuxt/vue/react/nextjs/full-stack/base)

If the script is not available, detect manually by reading:
- `composer.json` — PHP/Laravel dependencies
- `package.json` — Node.js/frontend dependencies
- `nuxt.config.ts` / `next.config.ts` — framework config
- `.env.example` or `.env` — database, cache, queue, payment keys
- `docker-compose.yml` — infrastructure setup

### Step 3: Architecture Analysis

Glob the project directory to understand its structure:

```
# Laravel
app/Models/*.php         → count models
app/Http/Controllers/    → count controllers
database/migrations/     → count migrations
routes/*.php             → count route files
app/Services/            → Services pattern?
app/Repositories/        → Repository pattern?
tests/                   → count tests

# Frontend
components/**/*.vue|tsx  → count components
pages/**/*.vue|tsx       → count pages
composables/             → composables pattern?
stores/                  → state management?
```

Determine:
- **Monolith** — backend + frontend views in one repo
- **API-only** — backend without frontend views
- **Monorepo** — `api/` + `frontend/` or `apps/` + `packages/`
- **Frontend SPA** — no backend, just frontend

### Step 4: Git Analysis

Read-only git commands to understand project history:

```bash
git -C "<path>" remote -v                    # remotes
git -C "<path>" branch -a                    # branches
git -C "<path>" log --oneline -10            # recent commits
git -C "<path>" shortlog -sn --no-merges | head -5  # top contributors
git -C "<path>" rev-list --count HEAD        # total commits
```

### Step 5: Determine MCP Profile

Map detected stack to MCP profile using the same mapping as scaffold:

| Detected Framework | MCP Profile |
|-------------------|-------------|
| Laravel | `laravel` |
| Laravel + ecommerce indicators | `ecommerce` |
| Nuxt | `nuxt` |
| Vue (without Nuxt) | `vue` |
| React (without Next) | `react` |
| Next.js | `nextjs` |
| Monorepo (Laravel + frontend) | `full-stack` |
| Other / Unknown | `base` |

### Step 6: Ecosystem Assignment

If `--ecosystem <name>` was provided:
1. Read `knowledge/ecosystems.json`
2. If ecosystem exists, add this project to it
3. If not, create the ecosystem and add this project

If no ecosystem flag, ask the user:
- "Create new ecosystem" → ask for name, then create
- "Join existing ecosystem" → show list, let user pick
- "Standalone (no ecosystem)" → skip

Ecosystem entry format:
```json
{
  "name": "project-name",
  "role": "api|frontend|admin|worker|docs|landing",
  "stack": "Laravel 11",
  "path": "/absolute/path/to/project"
}
```

### Step 7: User Confirmation

Present the analysis summary and ask to proceed:

```
═══ ARKA OS — Project Analysis ═══
Name:          <name>
Path:          <path>
Framework:     <framework> <version>
Language:      <language>
Architecture:  <type>
Stack:         <technologies>
Database:      <db>
Auth:          <auth>
Testing:       <testing>
Metrics:       <X> models, <Y> components, <Z> migrations, <W> tests
MCP Profile:   <profile> (<N> MCPs)
Ecosystem:     <ecosystem or "standalone">
Git:           <total commits>, <branches> branches, <contributors> contributors
═══════════════════════════════════

Proceed with onboarding? (Y/n)
```

### Step 8: Generate PROJECT.md

Create `PROJECT.md` in the project root with all detected context:

```markdown
# <name> — WizardingCode Project

## Stack
- **Framework:** <framework> <version>
- **Language:** <language>
- **Database:** <database>
- **Cache:** <cache>
- **Queue:** <queue>
- **Auth:** <auth>
- **Payments:** <payments>
- **CSS:** <css>
- **Testing:** <testing>

## Architecture
- **Type:** <monolith|api-only|monorepo|frontend-spa>
- **Patterns:** <Services, Repositories, etc.>

## Key Paths
- Models: `app/Models/`
- Controllers: `app/Http/Controllers/`
- Routes: `routes/`
- Migrations: `database/migrations/`
- Tests: `tests/`
- Components: `components/` or `src/components/`

## Conventions
- TypeScript: <yes/no>
- Linting: <ESLint/PHPStan/none>
- Formatting: <Prettier/none>
- Docker: <yes/no>

## Ecosystem
- **Ecosystem:** <name or "standalone">
- **Role:** <api/frontend/admin/worker>

## Current State
- Total commits: <N>
- Active branches: <list>
- Top contributors: <list>
- Last commit: <date and message>

## MCPs Active
- <list from applied profile>

## Decisions
- **Onboarded:** <date> via ARKA OS v<version>
- **MCP Profile:** <profile>
```

### Step 9: Register in ARKA OS

```bash
mkdir -p "$ARKA_OS/projects/<name>"
cp "<path>/PROJECT.md" "$ARKA_OS/projects/<name>/PROJECT.md"
echo "<absolute-path>" > "$ARKA_OS/projects/<name>/.project-path"
```

The `.project-path` file stores the absolute path so system commands like `/arka standup` can find and reference the actual project.

### Step 10: Apply MCP Profile

```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" <profile> --project "<path>"
```

This generates `.mcp.json` and `.claude/settings.local.json` in the project.

### Step 11: Create Obsidian Documentation

Create pages in the Obsidian vault at `{{OBSIDIAN_VAULT}}`:

**Home page:** `Projects/<name>/Home.md`
```markdown
---
type: project
name: <name>
stack:
  - <framework>
  - <language>
status: active
date_created: <YYYY-MM-DD>
ecosystem: <ecosystem or null>
tags:
  - project
  - <framework-kebab-case>
---

# <name>

> Onboarded into ARKA OS on <date>

## Overview
- **Framework:** <framework>
- **Architecture:** <type>
- **Stack:** <technologies>

## Architecture
- [[<name> - Architecture]]

## Links
- Local: `<path>`
- ARKA OS: `projects/<name>/PROJECT.md`

---
*Part of the [[Projects MOC]]*
```

**Architecture overview:** `Projects/<name>/Architecture/Overview.md`
```markdown
---
type: adr-log
project: <name>
date_created: <YYYY-MM-DD>
tags:
  - architecture
  - adr
---

# Architecture — <name>

## ADR-000: Project Onboarded
- **Date:** <today>
- **Decision:** Onboarded existing project into ARKA OS
- **Stack:** <full stack details>
- **Architecture:** <type> with <patterns>
- **MCP Profile:** <profile>
```

**Update Projects MOC:** Append `- [[<name>]]` to the Active Projects section.

**Ecosystem MOC** (if ecosystem assigned): Create or update `Projects/Ecosystems/<ecosystem>.md`:
```markdown
---
type: ecosystem
name: <ecosystem>
date_updated: <YYYY-MM-DD>
tags:
  - ecosystem
  - project
---

# <ecosystem> Ecosystem

## Projects
| Project | Role | Stack | Path |
|---------|------|-------|------|
| [[<name>]] | <role> | <stack> | `<path>` |

---
*Part of the [[Projects MOC]]*
```

### Step 12: Report

```
═══ ARKA OS — Project Onboarded ═══
Name:          <name>
Framework:     <framework>
Architecture:  <type>
MCPs:          <count> active (<profile> profile)
Ecosystem:     <ecosystem or "standalone">
PROJECT.md:    <path>/PROJECT.md
Obsidian:      Projects/<name>/Home.md
════════════════════════════════════

Next steps:
  cd <path>
  /dev feature "describe your first feature"
  /dev review    (review current code)
```

## Workflow: /dev ecosystem list

1. Read `knowledge/ecosystems.json`
2. Display all ecosystems with their projects:

```
═══ ARKA OS — Ecosystems ═══
<ecosystem-name>
  • <project> (<role>) — <stack> — <path>
  • <project> (<role>) — <stack> — <path>

<ecosystem-name>
  • <project> (<role>) — <stack> — <path>
═════════════════════════════
```

## Workflow: /dev ecosystem create <name>

1. Read `knowledge/ecosystems.json`
2. Create new ecosystem entry: `"<name>": { "projects": [] }`
3. Write back
4. Confirm creation

## Workflow: /dev ecosystem add <project> --to <ecosystem>

1. Read `knowledge/ecosystems.json`
2. Read `projects/<project>/PROJECT.md` to get stack info
3. Read `projects/<project>/.project-path` to get path
4. Ask user for role (api/frontend/admin/worker/docs/landing)
5. Add to ecosystem
6. Write back
7. Update Ecosystem MOC in Obsidian

## Error Handling

- If path doesn't exist: suggest common directories, ask for correct path
- If already onboarded: show existing PROJECT.md, ask if re-onboard
- If no git repo: skip git analysis steps, warn user
- If detection script fails: fall back to manual file inspection
- If MCP apply fails: warn but continue (MCPs can be applied later)
- If Obsidian vault not configured: skip Obsidian steps, warn user
