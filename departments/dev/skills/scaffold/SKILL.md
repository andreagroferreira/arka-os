---
name: arka-dev-scaffold
description: >
  Project scaffolding from real git starter repos: creates NEW Laravel, Nuxt,
  Vue, React, or Next.js projects with dependency installation, mandatory
  packages, MCP configuration, Laravel Herd linking, Obsidian pages, and
  initial commit; full-stack monorepo support. TRIGGER: "scaffold", "new
  project", "cria um projeto novo", "bootstrap", "começa um projeto Laravel",
  "setup project", "/dev scaffold". SKIP: bringing an EXISTING codebase into
  ARKA OS -> dev/onboard (analysis and registration, not creation); only
  adding MCPs to a current project -> dev/mcp.
---

# Project Scaffolding — ARKA OS Dev Department

Create new projects from real git repositories with full automation: dependencies, MCPs, Obsidian pages, and initial commit.

## Commands

<!-- Column convention: command | DESCRIPTION | repo. The registry
     generator (bin/arka-registry-gen) reads column 2 as the user-facing
     description — a repo URL there ships garbled command help (QG
     blocker, 2026-07-09). -->
| Command | Description | Git Repository |
|---------|-------------|----------------|
| `/dev scaffold laravel <name>` | Scaffold a Laravel app into ~/Herd from the starter repo | `https://${GIT_HOST}/laravel/laravel.git` (override with `ARKAOS_LARAVEL_STARTER_REPO` env) |
| `/dev scaffold nuxt-saas <name>` | Scaffold a Nuxt 3 SaaS dashboard into ~/Work | `https://github.com/nuxt-ui-templates/dashboard.git` |
| `/dev scaffold nuxt-landing <name>` | Scaffold a Nuxt 3 landing page into ~/Work | `https://github.com/nuxt-ui-templates/landing.git` |
| `/dev scaffold nuxt-docs <name>` | Scaffold a Nuxt 3 docs site into ~/Work | `https://github.com/nuxt-ui-templates/docs.git` |
| `/dev scaffold vue-saas <name>` | Scaffold a Vue 3 SaaS dashboard into ~/Work | `https://github.com/nuxt-ui-templates/dashboard-vue.git` |
| `/dev scaffold vue-landing <name>` | Scaffold a Vue 3 landing page into ~/Work | `https://github.com/nuxt-ui-templates/starter-vue.git` |
| `/dev scaffold full-stack <name>` | Scaffold Laravel (~/Herd) + Nuxt (~/Work) as a linked pair | Laravel + Nuxt starter repos above |
| `/dev scaffold react <name>` | Scaffold a React SPA — starter repo not yet selected | (not yet selected) |
| `/dev scaffold nextjs <name>` | Scaffold a Next.js app — starter repo not yet selected | (not yet selected) |

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

**Main page:** `${VAULT_PATH}/Projects/<name>/Home.md`
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

**Architecture page:** `${VAULT_PATH}/Projects/<name>/Architecture/decisions.md`
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

- If `git clone` fails: check SSH keys / repo access permissions for the configured `${GIT_HOST}`
- If `composer install` fails: check PHP version (`php -v`, need 8.3+)
- If `pnpm install` fails: check Node version (`node -v`, need 18+)
- If `herd link` fails: check Herd is installed and running
- If Boost install fails: continue with remaining packages, warn user
