# ARKA OS — WizardingCode Company Operating System

> AI-Powered Company OS. One system. Multiple departments. Infinite capability.

## Identity

- **Company:** WizardingCode
- **System:** ARKA OS
- **Owner:** Andrea Groferreira
- **Purpose:** AI-augmented company operating system that manages development, marketing, e-commerce, finance, operations, and strategy through specialized departments and personas

## Core Principles

1. **One System, Many Departments** — Everything lives here. No scattered projects.
2. **Personas Are Team Members** — Each agent has a name, personality, expertise, and opinion.
3. **Knowledge Compounds** — Every interaction can grow the knowledge base.
4. **Context Is King** — Always read project CLAUDE.md before working on a project.
5. **Action Over Theory** — Every output must be actionable, not academic.
6. **Client-Ready Always** — Reports, proposals, code — ready to deliver without editing.
7. **Obsidian Is The Brain** — ALL output goes to the Obsidian vault. No local files for knowledge.

## Tech Stack (Default)

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Laravel 11 (PHP 8.3) | Primary backend framework |
| Frontend | Vue 3 (Composition API) + TypeScript | Always `<script setup>` |
| SSR/Full-stack | Nuxt 3 | For full-stack apps |
| Database | PostgreSQL (via Supabase) | Default DB |
| CSS | Tailwind CSS | Utility-first |
| Python | Python 3.11+ | Scripts, AI, automation |
| Deploy | Vercel / Azure | Depends on project |
| Auth | Laravel Sanctum / Supabase Auth | Depends on project |
| Localhost | Laravel Herd | Always for Laravel projects |

## Coding Standards

- **Laravel:** Services + Repositories pattern, Form Requests, API Resources, Feature Tests
- **Vue/Nuxt:** Composition API only, TypeScript, composables for shared logic
- **Python:** Type hints, docstrings, virtual environments
- **Git:** Conventional commits, feature branches, PR reviews
- **Never:** Options API, raw SQL in controllers, business logic in controllers

## Laravel Mandatory Packages

Every new Laravel project MUST install these in order:

| # | Package | Post-Install | Notes |
|---|---------|-------------|-------|
| 1 | `laravel/boost` | `php artisan boost:install` | MUST be first — enables MCP |
| 2 | `laravel/horizon` | `php artisan horizon:install` | Queue monitoring |
| 3 | `echolabs/prism` | — | AI SDK (multi-provider LLM) |
| 4 | `php-mcp/laravel` | `php artisan vendor:publish` | MCP server for Laravel |

Config: `mcps/stacks/laravel-packages.json`

## Department Commands

| Department | Prefix | Purpose |
|-----------|--------|---------|
| Core System | `/arka` | System-level commands (standup, monitor, status, onboard) |
| Development | `/dev` | Code, build, deploy, review, scaffold, MCP management |
| Marketing | `/mkt` | Social media, content, affiliates, ads |
| E-commerce | `/ecom` | Store management, products, optimization |
| Finance | `/fin` | Financial planning, investment, negotiation |
| Operations | `/ops` | Automations, tasks, emails, calendar |
| Strategy | `/strat` | Market analysis, brainstorming, planning |
| Knowledge | `/kb` | Learn from content, build personas, search knowledge |

## Project Scaffolding

Create new projects from real git repositories:

| Command | Repository | MCP Profile |
|---------|-----------|-------------|
| `/dev scaffold laravel <name>` | `git@andreagroferreira:andreagroferreira/laravel-starter-kit.git` | laravel |
| `/dev scaffold nuxt-saas <name>` | `github.com/nuxt-ui-templates/dashboard.git` | nuxt |
| `/dev scaffold nuxt-landing <name>` | `github.com/nuxt-ui-templates/landing.git` | nuxt |
| `/dev scaffold nuxt-docs <name>` | `github.com/nuxt-ui-templates/docs.git` | nuxt |
| `/dev scaffold vue-saas <name>` | `github.com/nuxt-ui-templates/dashboard-vue.git` | vue |
| `/dev scaffold vue-landing <name>` | `github.com/nuxt-ui-templates/starter-vue.git` | vue |
| `/dev scaffold full-stack <name>` | Laravel + Nuxt (both repos) | full-stack |

Scaffolding auto-installs dependencies, mandatory packages, applies MCPs, links Herd, and creates Obsidian project page.

## MCP System

### Registry
Central catalog of all MCPs at `mcps/registry.json` (13 MCPs).

### Profiles
Pre-configured sets of MCPs applied per project type:

| Profile | MCPs |
|---------|------|
| `base` | obsidian, context7, playwright, memory-bank, sentry, gh-grep, clickup |
| `laravel` | base + laravel-boost, serena |
| `nuxt` | base + nuxt, nuxt-ui |
| `vue` | base + nuxt-ui |
| `ecommerce` | base + laravel-boost, serena, mirakl |
| `full-stack` | base + laravel-boost, serena, nuxt, nuxt-ui |

### Commands
- `/dev mcp apply <profile>` — Apply profile to project
- `/dev mcp add <name>` — Add single MCP
- `/dev mcp list` — Show all available MCPs
- `/dev mcp status` — Show active MCPs

### How It Works
`mcps/scripts/apply-mcps.sh` generates `.mcp.json` + `.claude/settings.local.json` in the target project.

## Obsidian Vault

**Path:** `/Users/andreagroferreira/Documents/Personal/`

ALL department output goes to this Obsidian vault. No local knowledge files.

### Conventions (match existing vault format)
- **Frontmatter:** YAML (type, name/title, tags, date)
- **Links:** Wikilinks `[[Note Name]]`
- **Tags:** kebab-case (`digital-marketing`, `laravel-project`)
- **MOC:** Map of Content pages (`Personas MOC`, `Topics MOC`, etc.)

### Department Output Paths

| Department | Vault Path |
|-----------|-----------|
| `/kb` | `Personas/`, `Sources/`, `Topics/`, `🧠 Knowledge Base/` |
| `/dev` | `Projects/<name>/Architecture/`, `Projects/<name>/Docs/` |
| `/mkt` | `WizardingCode/Marketing/` |
| `/ecom` | `WizardingCode/Ecommerce/` |
| `/fin` | `WizardingCode/Finance/` |
| `/ops` | `WizardingCode/Operations/` |
| `/strat` | `WizardingCode/Strategy/` |

Config: `knowledge/obsidian-config.json`

## Active Projects

Check `projects/` directory for project-specific context. Each project has:
- `PROJECT.md` — Full context (client, stack, decisions, conventions)
- Project-specific overrides to global standards
- Corresponding Obsidian page at `Projects/<name>/Home.md`

## Memory System

- **Obsidian Vault** — Primary knowledge store (personas, topics, sources, reports)
- **Memory Bank MCP** — Persistent session-to-session memory
- **projects/** — Project-specific context and decisions

## MCP Integrations (Global)

Active MCPs extend ARKA OS capabilities:

| MCP | Category | Purpose |
|-----|----------|---------|
| Obsidian | base | Vault read/write (Obsidian MCP) |
| Context7 | base | Up-to-date library documentation |
| Playwright | base | Browser automation and testing |
| Memory Bank | base | Persistent memory across sessions |
| Sentry | base | Error tracking and performance |
| GH Grep | base | Search across GitHub repos |
| ClickUp | base | Task management |
| Supabase | external | Database management |
| Shopify | external | E-commerce stores |
| Gmail | external | Email communication |
| Google Calendar | external | Scheduling |
| Google Drive | external | Document storage |
| Canva | external | Visual design |
| Chrome | external | Browser automation |

## How To Work

1. **Starting a task:** Read relevant department skill + project CLAUDE.md
2. **Making decisions:** Consult appropriate persona (CTO for tech, CFO for money)
3. **Learning something new:** Use `/kb learn` to add to knowledge base (→ Obsidian)
4. **Creating a project:** Use `/dev scaffold` to bootstrap from real repos
5. **Configuring MCPs:** Use `/dev mcp apply` for per-project MCP setup
6. **Cross-department work:** Skills can reference other departments
7. **All output → Obsidian:** Every report, analysis, and document goes to the vault
