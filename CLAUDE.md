# ARKA OS — WizardingCode Company Operating System

> AI-Powered Company OS. One system. Multiple departments. Infinite capability.

## Version

- **Current:** 0.2.0
- **Version file:** `VERSION`
- **Auto-update:** `version-check.sh` checks for updates once per 24h
- **Update:** Run `arka update` or `cd <repo> && git pull && bash install.sh`

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

## CLI Command

ARKA OS installs a global `arka` command:

| Command | Description |
|---------|-------------|
| `arka` | Open Claude Code with ARKA OS |
| `arka --version` | Show installed version |
| `arka update` | Pull latest + reinstall |
| `arka skill install <url>` | Install external skill |
| `arka skill list` | List external skills |
| `arka skill remove <name>` | Remove external skill |
| `arka skill update <name>` | Update external skill |
| `arka skill create <name>` | Scaffold new skill from template |

## Tech Stack (Default)

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Laravel 11 (PHP 8.3) | Primary backend framework |
| Frontend | Vue 3 (Composition API) + TypeScript | Always `<script setup>` |
| React | React 19 + Next.js 15 | For React-based projects |
| SSR/Full-stack | Nuxt 3 | For full-stack apps |
| Database | PostgreSQL (via Supabase) | Default DB |
| CSS | Tailwind CSS | Utility-first |
| Python | Python 3.11+ | Scripts, AI, automation |
| Deploy | Vercel / Azure | Depends on project |
| Auth | Laravel Sanctum / Supabase Auth / NextAuth | Depends on project |
| Localhost | Laravel Herd | Always for Laravel projects |

## Coding Standards

- **Laravel:** Services + Repositories pattern, Form Requests, API Resources, Feature Tests
- **Vue/Nuxt:** Composition API only, TypeScript, composables for shared logic
- **React/Next.js:** TypeScript, Server Components, App Router, shadcn/ui
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
| Development | `/dev` | Code, build, deploy, review, scaffold, MCP management, external skills |
| Marketing | `/mkt` | Social media, content, affiliates, ads |
| E-commerce | `/ecom` | Store management, products, optimization |
| Finance | `/fin` | Financial planning, investment, negotiation |
| Operations | `/ops` | Automations, tasks, emails, calendar, messaging channels |
| Strategy | `/strat` | Market analysis, brainstorming, planning |
| Knowledge | `/kb` | Learn from content, build personas, search knowledge |

## Project Scaffolding

Create new projects from real git repositories (9 types):

| Command | Repository | MCP Profile |
|---------|-----------|-------------|
| `/dev scaffold laravel <name>` | `git@andreagroferreira:andreagroferreira/laravel-starter-kit.git` | laravel |
| `/dev scaffold nuxt-saas <name>` | `https://github.com/nuxt-ui-templates/dashboard.git` | nuxt |
| `/dev scaffold nuxt-landing <name>` | `https://github.com/nuxt-ui-templates/landing.git` | nuxt |
| `/dev scaffold nuxt-docs <name>` | `https://github.com/nuxt-ui-templates/docs.git` | nuxt |
| `/dev scaffold vue-saas <name>` | `https://github.com/nuxt-ui-templates/dashboard-vue.git` | vue |
| `/dev scaffold vue-landing <name>` | `https://github.com/nuxt-ui-templates/starter-vue.git` | vue |
| `/dev scaffold full-stack <name>` | Laravel + Nuxt (both repos) | full-stack |
| `/dev scaffold react <name>` | React starter (TBD) | react |
| `/dev scaffold nextjs <name>` | Next.js starter (TBD) | nextjs |

Scaffolding auto-installs dependencies, mandatory packages, applies MCPs, links Herd, and creates Obsidian project page.

## MCP System

### Registry
Central catalog of all MCPs at `mcps/registry.json` (21 MCPs).

### Profiles
Pre-configured sets of MCPs applied per project type:

| Profile | MCPs |
|---------|------|
| `base` | obsidian, context7, playwright, memory-bank, sentry, gh-grep, clickup, firecrawl, supabase |
| `laravel` | base + laravel-boost, serena |
| `nuxt` | base + nuxt, nuxt-ui |
| `vue` | base + nuxt-ui |
| `react` | base + next-devtools |
| `nextjs` | base + next-devtools, supabase |
| `ecommerce` | base + laravel-boost, serena, mirakl, shopify-dev |
| `full-stack` | base + laravel-boost, serena, nuxt, nuxt-ui |
| `comms` | base + slack, discord, whatsapp, teams |

### Commands
- `/dev mcp apply <profile>` — Apply profile to project
- `/dev mcp add <name>` — Add single MCP
- `/dev mcp list` — Show all available MCPs
- `/dev mcp status` — Show active MCPs

### Environment Setup
Run `bash env-setup.sh` to interactively configure API keys for MCPs that require them (ClickUp, Firecrawl, PostgreSQL, Discord, WhatsApp, Teams).

### How It Works
`mcps/scripts/apply-mcps.sh` generates `.mcp.json` + `.claude/settings.local.json` in the target project.

## Messaging Integration

ARKA OS supports 4 messaging platforms via the `comms` MCP profile:

| Platform | MCP | Auth |
|----------|-----|------|
| Slack | `slack` | OAuth (no manual keys) |
| Discord | `discord` | `DISCORD_TOKEN` |
| WhatsApp | `whatsapp` | `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID` |
| Teams | `teams` | `TEAMS_APP_ID`, `TEAMS_APP_SECRET` |

**Channel management:**
- `/ops channel add <platform> <channel-id>` — Add messaging channel
- `/ops channel list` — List configured channels
- `/ops channel remove <platform>` — Remove channel
- `/ops notify <message>` — Send to default channel
- `/ops broadcast <message>` — Send to all channels

Config: `knowledge/channels-config.json`

## Community vs Pro

ARKA OS has two tiers:

### Community (this repo)
- 7 departments, 10 personas, 21 MCPs
- Full scaffolding (9 types), MCP management, Obsidian integration
- External skill system, CLI command, auto-updates

### Pro (private repo)
- Additional agents: growth-hacker, copywriter, data-analyst
- Premium skills: advanced-seo, funnel-builder
- Knowledge packs: saas-playbook
- Install: `bash pro-install.sh`
- Info: https://wizardingcode.com/arka-pro

**Naming convention:**

| Type | Prefix | Example |
|------|--------|---------|
| Built-in | `arka-` | `arka-cto.md`, `arka-dev/` |
| Pro | `arka-pro-` | `arka-pro-growth-hacker.md` |
| External | `arka-ext-` | `arka-ext-geo-seo/` |

Manifest: `pro-manifest.json`

## External Skills

Third-party skills can be installed from GitHub repos:

### Standard Format
```
my-skill/
  SKILL.md            (Required — Claude Code skill definition)
  arka-skill.json     (Required — metadata)
  agents/             (Optional — agent definitions)
  mcps/               (Optional — MCPs to register)
    registry-ext.json
```

### Commands
- `arka skill install <github-url>` — Install from GitHub
- `arka skill list` — List installed skills
- `arka skill remove <name>` — Uninstall
- `arka skill update <name>` — Update to latest
- `arka skill create <name>` — Scaffold from template
- `/dev skill add <url>` — Install via Claude Code
- `/dev skill list` — List via Claude Code
- `/dev skill remove <name>` — Remove via Claude Code
- `/dev skill create <name>` — Create via Claude Code

Full spec: `docs/SKILL-STANDARD.md`

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

## MCP Integrations

### ARKA OS MCPs (managed by the system — 21 in registry)

| MCP | Category | Purpose |
|-----|----------|---------|
| Obsidian | base | Vault read/write (Obsidian MCP) |
| Context7 | base | Up-to-date library documentation |
| Playwright | base | Browser automation and testing |
| Memory Bank | base | Persistent memory across sessions |
| Sentry | base | Error tracking and performance |
| GH Grep | base | Search across GitHub repos |
| ClickUp | base | Task management |
| Firecrawl | base | Web crawling and scraping |
| Supabase | base | Database management and APIs |
| Laravel Boost | laravel | AI-powered Laravel development tools |
| Serena | laravel | Code intelligence and refactoring |
| Nuxt UI | nuxt | Nuxt UI component library |
| Nuxt | nuxt | Nuxt framework documentation |
| Next DevTools | react | Next.js development tools |
| Mirakl | ecommerce | Mirakl marketplace API |
| Shopify Dev | ecommerce | Shopify development tools |
| Postgres | base | PostgreSQL direct database access |
| Slack | comms | Slack messaging (OAuth) |
| Discord | comms | Discord bot and messaging |
| WhatsApp | comms | WhatsApp Business API |
| Teams | comms | Microsoft Teams messaging |

### External MCPs (user environment — available if configured)

These MCPs are part of the user's Claude Code environment, not managed by ARKA OS:

| MCP | Purpose |
|-----|---------|
| Gmail | Email communication |
| Google Calendar | Scheduling |
| Google Drive | Document storage |
| Canva | Visual design |

## How To Work

1. **Starting a task:** Read relevant department skill + project CLAUDE.md
2. **Making decisions:** Consult appropriate persona (CTO for tech, CFO for money)
3. **Learning something new:** Use `/kb learn` to add to knowledge base (→ Obsidian)
4. **Creating a project:** Use `/dev scaffold` to bootstrap from real repos
5. **Configuring MCPs:** Use `/dev mcp apply` for per-project MCP setup
6. **Installing skills:** Use `arka skill install <url>` for external skills
7. **Messaging:** Use `/ops channel add` to configure, `/ops notify` to send
8. **Cross-department work:** Skills can reference other departments
9. **All output → Obsidian:** Every report, analysis, and document goes to the vault
