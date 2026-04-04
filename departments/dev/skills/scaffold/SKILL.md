---
name: arka-dev-scaffold
description: >
  Project scaffolding from real git repositories. Creates new Laravel, Nuxt, Vue, React, or
  Next.js projects with automated dependency installation, mandatory packages, MCP configuration,
  Laravel Herd linking, Obsidian project pages, and initial git commit. Full-stack monorepo support.
  Use when user says "scaffold", "new project", "create project", "start project", "bootstrap",
  "init project", "setup project", or wants to create a new codebase from a template.
---

# Project Scaffolding — ARKA OS Dev Department

Create new projects from real git repositories with full automation: dependencies, MCPs, Obsidian pages, and initial commit.

## Commands

| Command | Git Repository | Stack |
|---------|---------------|-------|
| `/dev scaffold laravel <name>` | `git@andreagroferreira:andreagroferreira/laravel-starter-kit.git` | Laravel + Herd |
| `/dev scaffold nuxt-saas <name>` | `https://github.com/nuxt-ui-templates/dashboard.git` | Nuxt 3 Dashboard |
| `/dev scaffold nuxt-landing <name>` | `https://github.com/nuxt-ui-templates/landing.git` | Nuxt 3 Landing |
| `/dev scaffold nuxt-docs <name>` | `https://github.com/nuxt-ui-templates/docs.git` | Nuxt 3 Docs |
| `/dev scaffold vue-saas <name>` | `https://github.com/nuxt-ui-templates/dashboard-vue.git` | Vue 3 Dashboard |
| `/dev scaffold vue-landing <name>` | `https://github.com/nuxt-ui-templates/starter-vue.git` | Vue 3 Landing |
| `/dev scaffold full-stack <name>` | Laravel + Nuxt (both repos) | Full-stack |
| `/dev scaffold react <name>` | React starter (TBD) | React SPA |
| `/dev scaffold nextjs <name>` | Next.js starter (TBD) | Next.js App |

## Workflow: /dev scaffold <type> <name>

### Step 1: Clone & Initialize

```bash
# Clone the template repo
git clone <repo-url> <name>
cd <name>

# Remove template git history and start fresh
rm -rf .git
git init
```

### Step 2: Install Dependencies

**For Laravel projects:**
```bash
composer install
```

**For Nuxt/Vue projects:**
```bash
pnpm install
```

**For full-stack:**
Both `composer install` (in `api/` or root) and `pnpm install` (in `frontend/` or root).

### Step 3: Laravel Mandatory Packages (Laravel projects only)

Read `mcps/stacks/laravel-packages.json` and install in ORDER:

```bash
# 1. Boost FIRST (enables laravel-boost MCP)
composer require laravel/boost
php artisan boost:install

# 2. Horizon
composer require laravel/horizon
php artisan horizon:install

# 3. Prism (AI SDK)
composer require echolabs/prism

# 4. MCP Server
composer require php-mcp/laravel
php artisan vendor:publish --provider="PhpMcp\Laravel\McpServiceProvider"
```

**IMPORTANT:** Boost MUST be installed first. It enables the laravel-boost MCP server.

### Step 4: Laravel Herd (Laravel projects only)

```bash
herd link
```

This registers the project with Laravel Herd for local serving at `http://<name>.test`.

### Step 5: Apply MCP Profile

Run the MCP applicator with the appropriate profile:

```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" <profile> --project "$(pwd)"
```

Profile mapping:
- `laravel` → `laravel` profile
- `nuxt-*` → `nuxt` profile
- `vue-*` → `vue` profile
- `full-stack` → `full-stack` profile

This generates `.mcp.json` and `.claude/settings.local.json`.

### Step 6: Generate PROJECT.md

Create `PROJECT.md` in the project root with:

```markdown
# <name> — WizardingCode Project

## Client
- **Name:** [ask user or leave TBD]
- **Type:** [project type]

## Stack
- [auto-detected from scaffold type]

## Conventions
- [inherit from ARKA OS CLAUDE.md defaults]

## Decisions
- [scaffold date and type recorded here]

## MCPs Active
- [list from applied profile]
```

Also register in ARKA OS:
```bash
mkdir -p "$ARKA_OS/projects/<name>"
cp PROJECT.md "$ARKA_OS/projects/<name>/PROJECT.md"
```

### Step 7: Create Obsidian Project Page

Create pages in the Obsidian vault:

**Main page:** `Documents/Personal/Projects/<name>/Home.md`
```markdown
---
type: project
name: <name>
client: TBD
stack: [auto-detected]
status: active
date_created: [today]
tags:
  - project
  - [stack-tag]
---

# <name>

> WizardingCode Project

## Overview
[To be filled]

## Architecture
- [[<name> - Architecture]]

## Links
- Local: `~/Projects/<name>/`
- *Part of the [[Projects MOC]]*
```

**Architecture page:** `Documents/Personal/Projects/<name>/Architecture/decisions.md`
```markdown
---
type: adr-log
project: <name>
date_created: [today]
tags:
  - architecture
  - adr
---

# Architecture Decisions — <name>

## ADR-001: Initial Stack Selection
- **Date:** [today]
- **Decision:** Scaffolded with [type] template
- **Rationale:** [based on project requirements]
```

### Step 8: Initial Git Commit

```bash
git add -A
git commit -m "Initial scaffold from ARKA OS ([type] template)"
```

### Step 9: Report

```
═══ ARKA OS — Project Scaffolded ═══
Name:        <name>
Type:        <type>
Stack:       [stack details]
MCPs:        [count] active ([profile] profile)
Herd:        http://<name>.test (Laravel only)
Obsidian:    Projects/<name>/Home.md
═════════════════════════════════════

Next steps:
  cd <name>
  /dev feature "describe your first feature"
```

## React / Next.js Handling

`/dev scaffold react <name>` and `/dev scaffold nextjs <name>`:

1. Clone template repo
2. `pnpm install`
3. Apply MCP profile (`react` or `nextjs`)
4. Generate PROJECT.md
5. Create Obsidian project page
6. Initial git commit

**No mandatory packages step** — React/Next.js projects use recommended packages from `mcps/stacks/react-packages.json` instead. Profile mapping:
- `react` → `react` profile
- `nextjs` → `nextjs` profile

## Full-Stack Special Handling

`/dev scaffold full-stack <name>` creates a monorepo:

```
<name>/
├── api/          ← Laravel backend (from laravel-starter-kit)
├── frontend/     ← Nuxt dashboard (from nuxt-ui-templates/dashboard)
├── .mcp.json     ← full-stack MCP profile
├── .claude/
│   └── settings.local.json
├── PROJECT.md
└── docker-compose.yml (if applicable)
```

Both directories get their respective dependencies installed, and the full-stack MCP profile covers both Laravel and Nuxt tools.

## Error Handling

- If `git clone` fails: check SSH keys (`git@andreagroferreira:` for private repos)
- If `composer install` fails: check PHP version (`php -v`, need 8.3+)
- If `pnpm install` fails: check Node version (`node -v`, need 18+)
- If `herd link` fails: check Herd is installed and running
- If Boost install fails: continue with remaining packages, warn user
