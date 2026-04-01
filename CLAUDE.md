# ARKA OS — WizardingCode Company Operating System

> AI-Powered Company OS. One system. Multiple departments. Infinite capability.

## Version

- **Current:** 1.1.0
- **Version file:** `VERSION`
- **Auto-update:** `version-check.sh` checks for updates once per 24h
- **Update:** Run `arka update` or `cd <repo> && git pull && bash install.sh`

## Identity

- **Company:** WizardingCode
- **System:** ARKA OS
- **Owner:** Andrea Groferreira
- **Purpose:** AI-augmented company operating system that manages development, marketing, e-commerce, finance, operations, strategy, and brand through specialized departments and personas

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
| `arka kb queue` | Show KB job queue (no Claude Code needed) |
| `arka kb status [job-id]` | Check KB job status (no Claude Code needed) |
| `arka kb capabilities` | Show available tools and API keys |
| `arka kb cleanup` | Remove old media files |
| `arka doctor` | Run health check system (16 checks) |
| `arka doctor --fix` | Run health checks with auto-repair |
| `arka doctor --json` | Output health checks as JSON |
| `arka gotchas` | Show top 10 recurring errors |
| `arka gotchas clear` | Reset gotchas tracking |
| `arka gotchas --json` | JSON output of gotchas |
| `arka commands` | List all available commands from registry |
| `arka commands rebuild` | Regenerate commands registry |
| `arka commands --json` | JSON output of commands registry |
| `arka team-balance` | Show DISC team balance distribution |
| `arka providers` | List all AI providers + models + configured status |
| `arka providers add <id>` | Add new provider (interactive) |
| `arka providers remove <id>` | Remove a provider |
| `arka providers add-model <provider> <model-id>` | Add model to existing provider |
| `arka providers add-key <ENV_VAR>` | Configure API key in ~/.arka-os/.env |
| `arka providers routing` | Show current routing chains |
| `arka providers --json` | JSON output |
| `arka test` | Run bats test suite |

## Plugins (Base for All Projects)

ARKA OS v1.0 ships with two Claude Code plugins pre-installed on every installation. These are system-wide (user-scoped) and available in all projects automatically.

### Superpowers (obra/superpowers)

Agentic skills framework that injects structured development workflows into Claude Code. Version 5.x, 115K+ stars.

**What it provides:**
- **Brainstorming** — Socratic design refinement before coding
- **Test-Driven Development** — Enforced RED-GREEN-REFACTOR cycle
- **Systematic Debugging** — 4-phase root cause analysis
- **Writing Plans** — Implementation plans with exact file paths and verification steps
- **Executing Plans** — Batch execution with human checkpoints
- **Subagent-Driven Development** — Per-task subagent dispatch with 2-stage review
- **Parallel Agents** — Concurrent subagent workflows
- **Git Worktrees** — Isolated workspace creation (Superpowers feature, not used by ARKA's branch workflow)
- **Code Review** — Pre-review checklist + senior reviewer agent
- **Verification** — Evidence-based completion verification

**Integration with ARKA OS:** Superpowers skills coexist with ARKA department skills. ARKA's CLAUDE.md takes precedence over Superpowers skill instructions (by design). ARKA uses standard git branches for isolation, not git worktrees.

**Marketplace:** `superpowers-marketplace` (obra/superpowers-marketplace)

### Claude-Mem (thedotmack/claude-mem)

Persistent memory system with vector search for Claude Code. Version 10.x.

**What it provides:**
- **Automatic Memory Capture** — Hooks on session lifecycle events capture decisions, patterns, and context
- **Vector Search** — Chroma vector DB for semantic memory retrieval
- **Progressive Disclosure** — Returns compact IDs first, fetch full details on demand (10x token savings)
- **MCP Search Server** — Memory search available as an MCP tool
- **Timeline Reports** — Temporal view of captured memories
- **Smart Exploration** — AI-powered codebase exploration with memory context

**Storage:** `~/.claude-mem/` (SQLite + Chroma vector DB)
**Runtime:** Requires Bun and uv (auto-installed by plugin)

**Integration with ARKA OS:** Claude-Mem's vector memory complements ARKA's 4-layer memory architecture. ARKA's agent memory (per-agent MEMORY.md files) stores role-specific context; Claude-Mem captures cross-session patterns and decisions automatically. The two systems are additive — ARKA provides structured, role-aware memory; Claude-Mem provides semantic, searchable memory.

**Marketplace:** `thedotmack` (thedotmack/claude-mem)

### Plugin Management

| Command | Description |
|---------|-------------|
| `claude plugin list` | List installed plugins |
| `claude plugin install <plugin>@<marketplace>` | Install a plugin |
| `claude plugin uninstall <plugin>` | Remove a plugin |
| `claude plugin update <plugin>` | Update a plugin |
| `claude plugin marketplace list` | List configured marketplaces |
| `claude plugin marketplace add <source>` | Add a marketplace |

### awesome-claude-code Reference

The [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) repository is a curated catalog of 200+ Claude Code resources (skills, hooks, CLAUDE.md templates, tools). Not installable — use as a discovery tool for evaluating additional plugins and skills.

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
- **SOLID (NON-NEGOTIABLE):** Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion — enforced on all code
- **Clean Code (NON-NEGOTIABLE):** Self-documenting names, no dead code, no magic numbers, no god classes, max 3 levels of nesting, functions under 30 lines
- **Never:** Options API, raw SQL in controllers, business logic in controllers
- **Enterprise workflow:** All `/dev feature` and `/dev api` commands follow a 10-phase workflow: specification → orchestration → research → architecture → implementation → self-critique ��� security audit → QA → documentation

## Development Branches (Mandatory)

All `/dev` commands that modify project code MUST run on a dedicated feature branch. This ensures branch isolation, prevents conflicts, and keeps main/dev branches clean.

**Enforced by:** `departments/dev/SKILL.md` — every code-modifying command starts with branch creation (`git checkout -b`)

**Commands requiring a feature branch:** `/dev feature`, `/dev api`, `/dev debug`, `/dev refactor`, `/dev db`

**Branch naming:**
| Type | Prefix | Example |
|------|--------|---------|
| Feature | `feature/` | `feature/user-auth` |
| Bug fix | `fix/` | `fix/login-crash` |
| Refactor | `refactor/` | `refactor/controllers` |

**Workflow:**
1. User runs `/dev feature "description"` (or similar)
2. System creates a branch: `git checkout -b feature/<slug>` (from `dev`)
3. All code changes happen on this isolated branch
4. Work is committed with conventional commit messages
5. A Merge Request is created targeting `dev`

## Spec-Driven Development (Mandatory)

All code-modifying dev commands (`/dev feature`, `/dev api`, `/dev db`, and code-modifying `/dev do`) require an approved spec before implementation begins. The spec is created interactively with the user and saved to Obsidian at `Projects/<name>/Specs/SPEC-<slug>.md`.

**Enforced by:** Constitution NON-NEGOTIABLE rule #7 + `departments/dev/skills/spec/SKILL.md`

**Commands:**
- `/dev spec <description>` — Create a feature spec interactively
- `/dev spec validate` — Validate existing spec completeness
- `/dev spec list` — List specs in current project

## Human Writing Standard (Mandatory)

All text output across all departments must read as naturally human-written. No AI patterns, no dashes as sentence connectors, perfect orthography, varied sentence structure. Respects the target language's tone and idiomatic expressions.

**Enforced by:** Constitution NON-NEGOTIABLE rule #8 + `arka/skills/human-writing/SKILL.md`

**Key rules:** No em-dashes as connectors, no "leverage/utilize/robust/streamline", correct accentuation in all languages, active voice by default, concrete facts over vague qualifiers.

## Squad Routing (Mandatory)

Every user request MUST be routed through the appropriate department squad. ARKA OS never responds as a generic assistant. Plain text input is equivalent to `/do` and is resolved to a department command via the registry. The orchestrator uses hook context (`[dept:]`, `[hint:]`), project context (CWD, PROJECT.md), and registry keyword matching to determine the correct squad, even when the user omits the command prefix.

**Enforced by:** Constitution NON-NEGOTIABLE rule #9 + `arka/SKILL.md` Squad Routing section

**Key rule:** There is no request "too simple" for squad routing. Even a one-line fix goes through the dev squad workflow.

## Laravel Mandatory Packages

Every new Laravel project MUST install these in order:

| # | Package | Post-Install | Notes |
|---|---------|-------------|-------|
| 1 | `laravel/boost` | `php artisan boost:install` | MUST be first — enables MCP |
| 2 | `laravel/horizon` | `php artisan horizon:install` | Queue monitoring |
| 3 | `echolabs/prism` | — | AI SDK (multi-provider LLM) |
| 4 | `php-mcp/laravel` | `php artisan vendor:publish` | MCP server for Laravel |

Config: `mcps/stacks/laravel-packages.json`

## Universal Orchestrator (/do)

Users don't need to memorize slash commands. Just describe what you need:
- "add user auth" → resolves to `/dev feature "user auth"`
- "create posts about AI" → resolves to `/mkt social "AI"`
- "audit my store" → resolves to `/ecom audit`

The `/do` command reads `knowledge/commands-registry.json` (generated from all SKILL.md files) to resolve natural language to the exact command. Plain text input uses the same resolution — typing without a slash prefix is equivalent to `/do`.

Key files:
- `knowledge/commands-registry.json` — Generated catalog (~119 commands)
- `knowledge/commands-keywords.json` — Hand-curated keyword/example data
- `bin/arka-registry-gen` — Registry generator script

## Department Commands

| Department | Prefix | Purpose |
|-----------|--------|---------|
| Universal | `/do` | Natural language → any command (universal orchestrator) |
| Core System | `/arka` | System-level commands (standup, monitor, status, onboard) |
| Development | `/dev` | Code, build, deploy, review, scaffold, plan, security-audit, research, onboard, MCP management, ecosystems, external skills |
| Marketing | `/mkt` | Social media, content, affiliates, ads |
| E-commerce | `/ecom` | Store management, products, optimization |
| Finance | `/fin` | Financial planning, investment, negotiation |
| Operations | `/ops` | Automations, tasks, emails, calendar, messaging channels |
| Strategy | `/strat` | Market analysis, brainstorming, planning |
| Knowledge | `/kb` | Async content learning, transcription queue, personas, search knowledge |
| Brand | `/brand` | Brand identity, colors, logos, mockups, photoshoots, videos, naming, positioning |

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

## Project Onboarding

Onboard existing projects (mid-development) into ARKA OS with automatic stack detection:

| Command | Description |
|---------|-------------|
| `/dev onboard <path>` | Auto-detect stack, generate PROJECT.md, apply MCPs, create Obsidian docs |
| `/dev onboard <path> --ecosystem <name>` | Onboard and assign to an ecosystem |

Onboarding runs a bundled Python script (`detect-stack.py`) that analyzes `composer.json`, `package.json`, `.env`, and directory structure to auto-detect framework, database, auth, payments, architecture patterns, and recommend the correct MCP profile. No manual input required.

## MCP System

### Registry
Central catalog of all MCPs at `mcps/registry.json` (22 MCPs).

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
| `brand` | base + canva |
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

## Extensible AI Provider System

ARKA OS includes an extensible provider registry for external AI services (image generation, video generation, text completion). Ships with 4 defaults but users can add ANY provider via CLI.

**Registry:** `config/providers-registry.json`

### Default Providers

| Provider | Models | Auth Env |
|----------|--------|----------|
| OpenAI | gpt-image-1, dall-e-3 | `OPENAI_API_KEY` |
| Replicate | flux-1.1-pro, sdxl, minimax-video | `REPLICATE_API_TOKEN` |
| FAL | flux-pro, kling-video, runway-gen3 | `FAL_KEY` |
| OpenRouter | gemini-2.5-pro, deepseek-r1, llama-4 | `OPENROUTER_API_KEY` |

### Routing Chains

Automatic fallback: picks the first provider with a configured API key.

- **image-generation:** OpenAI → FAL → Replicate
- **video-generation:** FAL → Replicate
- **text-completion:** OpenRouter

### CLI Commands

| Command | Description |
|---------|-------------|
| `arka providers` | List all providers + models + configured status |
| `arka providers add <id>` | Add new provider (interactive) |
| `arka providers remove <id>` | Remove a provider |
| `arka providers add-model <provider> <model-id>` | Add model to existing provider |
| `arka providers add-key <ENV_VAR>` | Configure API key |
| `arka providers routing` | Show routing chains |
| `arka providers --json` | JSON output |

### API Caller

`departments/brand/scripts/provider-call.sh` — generic API caller that reads provider config, resolves routing chains, and makes provider-specific API calls. Supports OpenAI, Replicate, FAL, and any OpenAI-compatible API.

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
- 8 departments, 19 personas, 22 MCPs, 2 plugins (Superpowers + Claude-Mem)
- Full scaffolding (9 types), MCP management, Obsidian integration
- External skill system, plugin system, CLI command, auto-updates
- 5-layer memory architecture (Obsidian + Agent Memory + Claude-Mem + Gotchas + Memory Bank)

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

**Path:** `{{OBSIDIAN_VAULT}}` (auto-detected during installation)

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
| `/brand` | `WizardingCode/Brand/` |

Config: `knowledge/obsidian-config.json`

## Active Projects

Check `projects/` directory for project-specific context. Each project has:
- `PROJECT.md` — Full context (client, stack, decisions, conventions)
- `.project-path` — Absolute path to the actual project directory
- Project-specific overrides to global standards
- Corresponding Obsidian page at `Projects/<name>/Home.md`

## Ecosystems

Group related projects (e.g., API + frontend + admin) into ecosystems:

| Command | Description |
|---------|-------------|
| `/dev ecosystem list` | List all ecosystems and their projects |
| `/dev ecosystem create <name>` | Create a new ecosystem |
| `/dev ecosystem add <project> --to <ecosystem>` | Add project to ecosystem |

Each project in an ecosystem has a role: `api`, `frontend`, `admin`, `worker`, `docs`, `landing`.

Config: `knowledge/ecosystems.json`

## Enhanced Status Line

Two-line color-coded display showing session context and metrics:

```
▲ARKA  project-name  on feature/auth  [wt:feat-auth]  |  Opus 4.6
██████░░░░ 62%  |  145K in 5.2K out  |  +50 -10  |  3m25s  |  $1.23
```

**Features:**
- Color-coded context bar: green <60%, yellow 60-79%, red 80-89%, blinking red 90%+
- Token count in K/M format from `context_window.total_input_tokens`
- Smart git branch: hidden on `main`/`master`
- Feature branch indicator: shown when on a non-main/dev branch
- Cached git operations: `/tmp/arka-statusline-git-cache` (5s TTL)

Config: `config/statusline.sh`

## Constitution

`CONSTITUTION.md` defines governance rules with 3 enforcement levels:

- **NON-NEGOTIABLE** (13 rules): Branch isolation, Obsidian output, authority boundaries, security gate, context-first, SOLID + Clean Code, spec-driven development, human writing, squad routing, full visibility, sequential task validation, mandatory complete QA, ARKA OS supremacy
- **QUALITY GATE** (mandatory): Marta (CQO) orchestrates Eduardo (Copy Director) + Francisca (Tech/UX Director). Absolute veto power. Nothing ships without APPROVED verdict from all three.
- **MUST** (5 rules): Conventional commits, test coverage ≥80%, pattern matching, actionable output, memory persistence
- **SHOULD** (4 rules): Research before building, self-critique, KB contribution, complexity assessment

Compressed version injected as L0 context layer via UserPromptSubmit hook.

## Agent Tier Hierarchy

All 22 agents have tier assignments and authority matrices in their YAML frontmatter:

| Tier | Role | Agents |
|------|------|--------|
| 0 (Chief) | Veto power, final decisions | CTO Marco, CFO Helena, COO Sofia, CQO Marta, Eduardo (Copy), Francisca (Tech/UX) |
| 1 (Lead) | Orchestrate, design, recommend | Tech Lead Paulo, Architect Gabriel, Luna, Ricardo, Tomas, Clara, Valentina |
| 2 (Specialist) | Implement within boundaries | Andre, Diana, Bruno, Carlos, Mateus, Isabel, Rafael |
| 3 (Support) | Validate, research, document | QA Rita, Analyst Lucas |

Authority fields: `veto`, `push`, `deploy`, `block_release`, `block_delivery`, `approve_architecture`, `approve_quality`, etc.

## Quality Gate Department

Cross-department quality supervision with absolute veto power. Three Tier 0 agents that review ALL output from ALL departments before delivery:

| Agent | Role | Scope |
|-------|------|-------|
| **Marta (CQO)** | Chief Quality Officer | Orchestrates quality review, aggregates verdicts, issues final APPROVED/REJECTED |
| **Eduardo** | Copy & Language Director | ALL text: spelling, grammar, accentuation, tone, AI patterns, factual accuracy |
| **Francisca** | Technical & UX Director | ALL technical: code quality, tests, UX/UI, data integrity, security, performance |

**Enforcement:** Quality Gate runs on EVERY workflow. No output reaches the user without Marta's APPROVED verdict. Rejected work loops back to execution with exact issue list.

Agent files: `departments/quality/agents/`

## DISC Behavioral Framework

All 22 agents have DISC behavioral profiles in their YAML frontmatter (`disc:` block) and a "Behavioral Profile" section covering communication style, behavior under pressure, motivation, feedback style, and conflict approach.

### DISC Profiles
- **D (Dominant):** Fast-paced, task-focused, results-driven
- **I (Influential):** Fast-paced, people-focused, enthusiasm-driven
- **S (Steady):** Measured-pace, people-focused, stability-driven
- **C (Conscientious):** Deliberate-pace, task-focused, quality-driven

### Agent DISC Mapping

| Agent | Primary | Secondary | Label |
|-------|---------|-----------|-------|
| Marco (CTO) | D | C | Driver-Analyst |
| Paulo (Tech Lead) | I | S | Inspirer-Supporter |
| Gabriel (Architect) | C | D | Analyst-Driver |
| Andre (Backend) | C | S | Analyst-Supporter |
| Diana (Frontend) | I | C | Inspirer-Analyst |
| Bruno (Security) | C | D | Analyst-Driver |
| Carlos (DevOps) | D | C | Driver-Analyst |
| Rita (QA) | C | S | Analyst-Supporter |
| Lucas (Analyst) | C | I | Analyst-Inspirer |
| Helena (CFO) | D | C | Driver-Analyst |
| Sofia (COO) | S | C | Supporter-Analyst |
| Luna (Content) | I | D | Inspirer-Driver |
| Ricardo (E-commerce) | D | I | Driver-Inspirer |
| Tomas (Strategy) | I | D | Inspirer-Driver |
| Clara (Knowledge) | S | C | Supporter-Analyst |
| Valentina (Brand) | S | I | Supporter-Inspirer |
| Mateus (Brand) | C | I | Analyst-Inspirer |
| Isabel (Brand) | I | S | Inspirer-Supporter |
| Rafael (Brand) | D | I | Driver-Inspirer |
| Marta (CQO) | C | D | Analyst-Driver |
| Eduardo (Copy Director) | C | S | Analyst-Supporter |
| Francisca (Tech/UX Director) | D | C | Driver-Analyst |

**Distribution:** D:6, I:5, S:3, C:8 — 22 agents across 9 departments. C profile dominant (36%) reflecting quality-driven culture.

### Key Files
- **Reference:** `config/disc-profiles.json` — 4 profiles, 10 combinations, team balance ideal ranges
- **Registry:** `knowledge/agents-registry.json` — Machine-readable manifest of all 22 agents with DISC data
- **Validator:** `config/disc-team-validator.sh` — Team balance checker
- **CLI:** `arka team-balance` — Display team DISC distribution

### Conflict Resolution (DISC-Informed)
Defined in `CONSTITUTION.md`: D vs D (data wins), C vs C (thoroughness wins), D vs C (goal+method split), I vs S (pace compromise). Escalation: same dept → Tier 0, cross-dept → COO Sofia.

## Agent Memory System

Each agent has persistent memory at `~/.claude/agent-memory/arka-<name>/MEMORY.md`:

- **Key Decisions** — Important decisions from sessions
- **Recurring Patterns** — Code styles, user preferences, workflows
- **Gotchas** — Errors encountered repeatedly + fixes
- **Learned Preferences** — User and project preferences
- **Project-Specific Notes** — Notes tied to specific projects

Template: `config/agent-memory-template.md`
Install creates 15 memory files, never overwrites existing ones.

## Hooks System

ARKA OS uses Claude Code hooks for contextual intelligence:

### UserPromptSubmit Hook (6-Layer Context Injection)
Injects 6 cached context layers per prompt (10s timeout, target <200ms):

| Layer | Source | Content | Cache TTL |
|-------|--------|---------|-----------|
| L0 | `CONSTITUTION.md` | Compressed non-negotiable rules | 300s |
| L1 | Signal word matching | Detected department name | None |
| L2 | Agent memory files | Agent name + last 3 gotchas | 30s |
| L3 | PROJECT.md / .project-path | Project name + stack info | 30s |
| L4 | Git branch detection | Active feature branch | None |
| L5 | `commands-registry.json` | Command hints for non-slash prompts | 30s |
| + | `gotchas.json` | Top 2 recurring errors for department (count ≥3) | 30s |
| + | `date +%H` | Time of day | None |

Cache directory: `/tmp/arka-context-cache/`
Config: `config/hooks/user-prompt-submit.sh`

### PostToolUse Hook (Gotchas Memory)
Tracks recurring errors from tool output (5s timeout):
- Detects errors from exit code ≠ 0 or error patterns in output
- Normalizes error patterns (removes timestamps, hashes)
- Categorizes: laravel, frontend, git, database, permissions, testing, general
- Stores in `~/.arka-os/gotchas.json` with `flock` for concurrent safety
- Keeps top 100 gotchas sorted by count

Config: `config/hooks/post-tool-use.sh`

### PreCompact Hook
Saves session digest before context compaction (30s timeout):
- Extracts last 5 assistant messages
- Saves markdown digest to `~/.arka-os/session-digests/`
- Auto-cleanup: keeps only last 50 digests
- No LLM analysis — raw context preservation

Config: `config/hooks/pre-compact.sh`

## Gotchas System

Recurring error tracking across sessions:

| Command | Description |
|---------|-------------|
| `arka gotchas` | Show top 10 recurring errors |
| `arka gotchas clear` | Reset gotchas file |
| `arka gotchas --json` | JSON output |

Storage: `~/.arka-os/gotchas.json` — JSON array of pattern, category, count, first/last seen, projects.
Populated automatically by the PostToolUse hook.

## Install Manifest

`~/.arka-os/install-manifest.json` tracks all installed files with SHA256 checksums:

- Generated at end of `install.sh`
- On update: compares checksums to detect user-customized files
- Used by `arka doctor` (check 14) to verify installation integrity

## Testing

ARKA OS uses [bats-core](https://github.com/bats-core/bats-core) for testing:

| Command | Description |
|---------|-------------|
| `arka test` | Run full test suite |
| `bats tests/` | Run directly |

Test files: `tests/cli.bats`, `tests/hooks.bats`, `tests/doctor.bats`, `tests/statusline.bats`, `tests/disc.bats`, `tests/orchestrator.bats`, `tests/brand.bats`, `tests/constitution.bats`
CI: `.github/workflows/test.yml` (runs on push/PR to master)

## Doctor System

`arka doctor [--fix] [--json]` — 16 modular health checks:

| # | Check | Type | What |
|---|-------|------|------|
| 1 | `claude-cli` | fail | Claude Code CLI installed |
| 2 | `arka-install` | fail | ARKA OS version + SKILL.md |
| 3 | `jq` | fail | jq available |
| 4 | `profile` | warn | User profile exists + has name |
| 5 | `statusline` | warn | Status line configured in settings.json |
| 6 | `hooks` | warn | Hooks configured in settings.json |
| 7 | `obsidian` | warn | Vault path exists and is valid |
| 8 | `departments` | warn | 7+ department skills installed |
| 9 | `personas` | warn | 10+ agent files installed |
| 10 | `mcp-registry` | fail | MCP registry.json present |
| 11 | `prerequisites` | warn | yt-dlp, ffmpeg, python3 |
| 12 | `capabilities` | warn | capabilities.json < 7 days old |
| 13 | `agent-memory` | warn | 22 agent memory files exist |
| 14 | `install-manifest` | warn | Manifest exists and valid |
| 15 | `gotchas` | warn | Gotchas file exists and is valid JSON |
| 16 | `plugins` | warn | Superpowers + Claude-Mem plugins installed |

- `--fix` attempts auto-repair (profile, statusline, hooks, capabilities)
- `--json` outputs JSON array for programmatic use

Config: `bin/arka-doctor`

## Capabilities System

ARKA OS detects available tools and API keys via `~/.arka-os/capabilities.json`. This file is generated by `kb-check-capabilities.sh` and updated during install, env-setup, and before `/kb learn`.

**Detected binaries:** `whisper`, `yt-dlp`, `ffmpeg`, `jq`, `python3`
**Detected API keys:** `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
**Transcription fallback chain:** local whisper > OpenAI Whisper API > download-only

Commands:
- `arka kb capabilities` — Show capabilities from terminal
- `/kb capabilities` — Show capabilities in Claude Code

Config: `~/.arka-os/capabilities.json`

## KB Async Processing

The Knowledge Base processes YouTube videos asynchronously. Downloads and transcriptions run as background jobs (`nohup`), allowing the user to continue working.

| Command | Description |
|---------|-------------|
| `/kb learn <url> [url2 ...] [--persona "Name"]` | Queue URLs for async download + transcription |
| `/kb queue` | Show all jobs and their status |
| `/kb status [job-id]` | Detailed status of a specific job |
| `/kb process <job-id>` | Interactively analyze a ready transcription |
| `/kb process --all` | Process all ready jobs |
| `/kb capabilities` | Show available tools and API keys |
| `/kb cleanup [--older-than 90d]` | Remove old completed media files |

**Job status flow:** `queued` → `downloading` → `transcribing` → `ready` → `analyzing` → `completed`

The `ready` → `analyzing` transition requires Claude Code (LLM analysis with 5 parallel agents).

## Media Storage

KB media files are stored permanently in `~/.arka-os/media/`, organized by date:

```
~/.arka-os/media/
├── 2026-03-15/
│   ├── a1b2c3d4/          # Job ID
│   │   ├── metadata.json  # Video title, duration
│   │   ├── audio.wav      # Downloaded audio
│   │   ├── audio.txt      # Transcription
│   │   └── worker.log     # Process log
```

State tracking: `~/.arka-os/kb-jobs.json` (all jobs, all statuses, concurrent-safe via `flock`)

Cleanup: `/kb cleanup --older-than 90d` removes completed job media older than 90 days.

## Memory System

ARKA OS has a 5-layer memory architecture:

- **Obsidian Vault** — Primary knowledge store (personas, topics, sources, reports)
- **Agent Memory** — Per-agent persistent memory at `~/.claude/agent-memory/arka-<name>/MEMORY.md` (22 files, one per agent). Stores key decisions, recurring patterns, gotchas, learned preferences, and project-specific notes. Never overwritten on update.
- **Claude-Mem (Vector Memory)** — Semantic vector search memory via Claude-Mem plugin. Auto-captures decisions and patterns across sessions. Storage at `~/.claude-mem/` (SQLite + Chroma). Provides progressive disclosure search (compact IDs → full details) for 10x token savings.
- **Gotchas** — Recurring error tracking at `~/.arka-os/gotchas.json`. Auto-populated by PostToolUse hook, surfaced via L0 context injection and `arka gotchas` CLI.
- **Memory Bank MCP** — Persistent session-to-session memory
- **projects/** — Project-specific context and decisions

## MCP Integrations

### ARKA OS MCPs (managed by the system — 22 in registry)

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
| Canva | brand | Canva design platform — create, edit, export designs |

### External MCPs (user environment — available if configured)

These MCPs are part of the user's Claude Code environment, not managed by ARKA OS:

| MCP | Purpose |
|-----|---------|
| Gmail | Email communication |
| Google Calendar | Scheduling |
| Google Drive | Document storage |
| Canva | Visual design |

## File Structure (v1.1.0)

```
arka-os/
├── CLAUDE.md                         # System instructions (this file)
├── CONSTITUTION.md                   # Governance rules (3 enforcement levels)
├── VERSION                           # Semver version (1.1.0)
├── install.sh                        # Installer (hooks fix, agent memory, manifest)
├── bin/
│   ├── arka                          # CLI wrapper (gotchas, test, doctor, kb, commands)
│   ├── arka-doctor                   # Health check (16 checks)
│   ├── arka-registry-gen             # Commands registry generator
│   ├── arka-providers               # AI provider management CLI
│   └── arka-skill                    # External skill manager
├── config/
│   ├── settings-template.json        # Claude settings (statusLine + 3 hooks)
│   ├── statusline.sh                 # Two-line status bar
│   ├── system-prompt.sh              # Dynamic system prompt
│   ├── agent-memory-template.md      # Per-agent memory template
│   ├── disc-profiles.json            # DISC framework reference (4 profiles, combinations, balance)
│   ├── disc-team-validator.sh        # Team DISC balance validator script
│   ├── providers-registry.json      # Extensible AI provider/model catalog
│   └── hooks/
│       ├── user-prompt-submit.sh     # 6-layer context injection
│       ├── post-tool-use.sh          # Gotchas error tracking
│       └── pre-compact.sh            # Session digest preservation
├── arka/
│   ├── SKILL.md                      # Main orchestrator
│   └── skills/
│       └── human-writing/SKILL.md    # Core writing quality gate (NON-NEGOTIABLE)
├── departments/
│   ├── dev/agents/                   # 9 dev agents (cto, tech-lead, architect, ...)
│   ├── dev/skills/spec/SKILL.md      # Spec-driven development gate (NON-NEGOTIABLE)
│   ├── finance/agents/cfo.md         # Helena
│   ├── operations/agents/coo.md      # Sofia
│   ├── marketing/agents/             # Luna
│   ├── ecommerce/agents/             # Ricardo
│   ├── strategy/agents/              # Tomas
│   ├── knowledge/agents/             # Clara
│   ├── brand/agents/                # Valentina, Mateus, Isabel, Rafael
│   └── quality/agents/              # Marta (CQO), Eduardo (Copy), Francisca (Tech/UX)
├── tests/
│   ├── helpers/setup.bash            # Common test helpers
│   ├── cli.bats                      # CLI routing tests
│   ├── hooks.bats                    # Hook contract tests
│   ├── doctor.bats                   # Doctor check tests
│   ├── statusline.bats              # Status line tests
│   ├── disc.bats                    # DISC framework tests
│   ├── orchestrator.bats            # Universal orchestrator tests
│   ├── brand.bats                   # Brand department + provider tests
│   └── constitution.bats            # Constitution rules + new skills tests
├── .github/workflows/test.yml        # CI (bats-core on push/PR)
└── docs/                             # User-facing documentation
```

**Runtime files (not in repo):**
```
~/.claude/agent-memory/arka-*/MEMORY.md   # 22 agent memory files
~/.claude/plugins/                         # Claude Code plugins (superpowers, claude-mem)
~/.claude-mem/                             # Claude-Mem vector DB (SQLite + Chroma)
~/.arka-os/gotchas.json                    # Recurring error patterns
~/.arka-os/install-manifest.json           # SHA256 checksums of installed files
~/.arka-os/capabilities.json               # Detected tools and API keys
~/.arka-os/session-digests/                # Pre-compact session digests
/tmp/arka-context-cache/                   # Hook layer caches (TTL-based)
```

## How To Work

1. **Starting a task:** Read relevant department skill + project CLAUDE.md
2. **Making decisions:** Consult appropriate persona (CTO for tech, CFO for money). Respect agent tier hierarchy — only Tier 0 can veto.
3. **Learning something new:** Use `/kb learn` to add to knowledge base (→ Obsidian)
4. **Creating a project:** Use `/dev scaffold` to bootstrap from real repos
5. **Configuring MCPs:** Use `/dev mcp apply` for per-project MCP setup
6. **Installing skills:** Use `arka skill install <url>` for external skills
7. **Messaging:** Use `/ops channel add` to configure, `/ops notify` to send
8. **Cross-department work:** Skills can reference other departments
9. **All output → Obsidian:** Every report, analysis, and document goes to the vault
10. **Tracking errors:** Gotchas are auto-tracked by PostToolUse hook. Review with `arka gotchas`.
11. **Running tests:** Use `arka test` to run the bats test suite
12. **Health checks:** Use `arka doctor` to verify system integrity (16 checks)
13. **Constitution:** All agents follow `CONSTITUTION.md` rules. NON-NEGOTIABLE rules cannot be bypassed.
