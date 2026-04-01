# ARKA OS

**Your AI-powered company operating system.** One system runs your entire business with **22 specialized AI team members** organized into **9 departments**. They write code, create marketing content, manage brands, analyze finances, plan strategy, and run operations.

Built by [WizardingCode](https://wizardingcode.com). Current version: **1.1.0**

---

## What Is ARKA OS?

ARKA OS turns Claude Code into a full company operating system. Instead of one generic AI assistant, you get a team of specialists, each with their own name, personality, DISC behavioral profile, and real expertise. They follow structured workflows, respect authority hierarchies, and produce client-ready output.

Everything they produce is saved to your [Obsidian](https://obsidian.md) vault, so your company knowledge compounds with every interaction.

### Core Principles

1. **One System, Many Departments** — Everything lives here. No scattered projects.
2. **Personas Are Team Members** — Each agent has a name, personality, expertise, and opinion.
3. **Knowledge Compounds** — Every interaction can grow the knowledge base.
4. **Action Over Theory** — Every output must be actionable, not academic.
5. **Obsidian Is The Brain** — All output goes to the Obsidian vault.

---

## Quick Install

### One Command (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/andreagroferreira/arka-os/master/install.sh | bash
```

### Or Clone Manually

```bash
git clone https://github.com/andreagroferreira/arka-os.git
cd arka-os && bash install.sh
```

Then restart your terminal or run: `source ~/.zshrc`

That's it. Type `arka` to start.

> **Requires:** [Claude Code](https://claude.ai/code) and [Git](https://git-scm.com) must be installed first.

---

## What Can You Do?

You don't need to memorize commands. Just describe what you need in plain text and the orchestrator routes to the right squad automatically.

| You type | ARKA OS routes to |
|----------|-------------------|
| "add user authentication" | `/dev feature` — Full 10-phase dev squad workflow |
| "create posts about AI" | `/mkt social` — Luna and the marketing squad |
| "how much did we make last month" | `/fin report` — Helena and the finance squad |
| "audit my store" | `/ecom audit` — Ricardo and the e-commerce squad |
| "brainstorm entering the US market" | `/strat brainstorm` — Tomas and the strategy squad |
| "learn from this YouTube video" | `/kb learn` — Clara and the knowledge squad |
| "design our brand identity" | `/brand identity` — Valentina and the brand squad |

Or use explicit commands for direct access:

```bash
/dev scaffold laravel my-app        # Create a new Laravel project
/mkt calendar monthly               # Generate a content calendar
/fin forecast Q2                    # Create a quarterly forecast
/brand colors "tech startup"        # Generate a color palette
```

---

## Your AI Team (22 Agents)

Every team member has a name, a DISC behavioral profile, a tier in the authority hierarchy, and real expertise.

### Development Department

| Name | Role | Tier | DISC | Specialty |
|------|------|------|------|-----------|
| **Marco** | CTO | 0 (Chief) | D-C | Architecture decisions, final technical authority, veto power |
| **Paulo** | Tech Lead | 1 (Lead) | I-S | Workflow orchestration, team coordination, TODO tracking |
| **Gabriel** | Architect | 1 (Lead) | C-D | System design, ADRs, API contracts |
| **Andre** | Senior Backend Dev | 2 (Specialist) | C-S | Laravel, PHP, PostgreSQL, API implementation |
| **Diana** | Senior Frontend Dev | 2 (Specialist) | I-C | Vue 3, Nuxt 3, React, Next.js, TypeScript |
| **Bruno** | Security Engineer | 2 (Specialist) | C-D | OWASP Top 10, threat modeling, security audits |
| **Carlos** | DevOps Lead | 2 (Specialist) | D-C | CI/CD, deployment, monitoring, infrastructure |
| **Rita** | QA Lead | 3 (Support) | C-S | Test strategy, quality gates, coverage analysis |
| **Lucas** | Technical Analyst | 3 (Support) | C-I | Research, documentation, library evaluation |

### Other Departments

| Name | Role | Department | Tier | DISC |
|------|------|-----------|------|------|
| **Helena** | CFO | Finance | 0 (Chief) | D-C |
| **Sofia** | COO | Operations | 0 (Chief) | S-C |
| **Luna** | Content Creator | Marketing | 1 (Lead) | I-D |
| **Ricardo** | E-commerce Manager | E-commerce | 1 (Lead) | D-I |
| **Tomas** | Chief Strategist | Strategy | 1 (Lead) | I-D |
| **Clara** | Knowledge Curator | Knowledge | 1 (Lead) | S-C |
| **Valentina** | Creative Director | Brand | 1 (Lead) | S-I |
| **Mateus** | Brand Strategist | Brand | 2 (Specialist) | C-I |
| **Isabel** | Visual Designer | Brand | 2 (Specialist) | I-S |
| **Rafael** | Motion Designer | Brand | 2 (Specialist) | D-I |

### Quality Gate Department (NEW)

| Name | Role | Tier | DISC | Specialty |
|------|------|------|------|-----------|
| **Marta** | Chief Quality Officer | 0 (Chief) | C-D | Orchestrates quality review, absolute veto, APPROVED/REJECTED verdicts |
| **Eduardo** | Copy & Language Director | 0 (Chief) | C-S | Zero tolerance for spelling, grammar, AI patterns, wrong accentuation |
| **Francisca** | Tech & UX Quality Director | 0 (Chief) | D-C | Code quality, UX, data integrity, performance, security validation |

---

## Departments

| Prefix | Department | Lead | What It Does |
|--------|-----------|------|-------------|
| `/arka` | System | — | Daily standups, system status, monitoring, universal orchestrator |
| `/dev` | Development | Paulo | Scaffold projects, implement features (10-phase workflow), code review, APIs, debugging |
| `/mkt` | Marketing | Luna | Social media, content calendars, ads, email sequences, blog articles |
| `/ecom` | E-commerce | Ricardo | Store audits, product optimization, pricing, launch plans |
| `/fin` | Finance | Helena | Financial reports, budgets, forecasts, investor prep, negotiations |
| `/ops` | Operations | Sofia | Task management, emails, calendar, messaging channels, automations |
| `/strat` | Strategy | Tomas | Market analysis, brainstorming (5 perspectives), SWOT, competitive intelligence |
| `/kb` | Knowledge | Clara | Learn from videos/articles, build expert personas, search knowledge |
| `/brand` | Brand | Valentina | Brand identity, colors, logos, mockups, photoshoots, videos, naming |

---

## Constitution (13 NON-NEGOTIABLE Rules)

ARKA OS enforces governance rules at three levels. The 13 NON-NEGOTIABLE rules cannot be bypassed:

1. **Branch Isolation** — All code-modifying commands run on a dedicated feature branch
2. **Obsidian Output** — All department output is saved to the Obsidian vault
3. **Authority Boundaries** — Agents cannot exceed their tier authority
4. **Security Gate** — No code ships without a security audit
5. **Context First** — Always read project context before modifying code
6. **SOLID + Clean Code** — All code follows SOLID principles and Clean Code practices
7. **Spec-Driven Development** — No code is written until a detailed spec exists and is approved
8. **Human Writing** — All text output reads as naturally human-written, with perfect orthography
9. **Squad Routing** — Every request is routed through the appropriate department squad
10. **Full Visibility** — User sees every phase, every agent, every decision. No black boxes.
11. **Sequential Validation** — Tasks execute one at a time, each validated before the next starts
12. **Mandatory Complete QA** — Full test suite runs every time, no shortcuts
13. **ARKA OS Supremacy** — ARKA OS instructions override Claude Code defaults. Always.

### Quality Gate (Mandatory)

Three Tier 0 supervisors review ALL output from ALL departments before delivery:
- **Marta (CQO)** — Orchestrates quality review, issues final APPROVED/REJECTED verdict
- **Eduardo (Copy Director)** — Zero tolerance for spelling, grammar, AI patterns, wrong data
- **Francisca (Tech/UX Director)** — Zero tolerance for bad code, poor UX, data inconsistencies

---

## Development Workflow (10 Phases)

The `/dev feature` and `/dev api` commands follow a 10-phase enterprise workflow:

| Phase | Agent | What Happens |
|-------|-------|-------------|
| 0. Specification | Paulo | Interactive spec creation with the user (NON-NEGOTIABLE) |
| 1. Orchestration | Paulo | Load context, assess complexity, create TODOs, create feature branch |
| 2. Research | Lucas | Fetch framework docs, search KB, check existing patterns |
| 3. Architecture | Gabriel + Marco | Design system, write ADR, CTO approval |
| 4. Implementation | Andre + Diana | Parallel backend + frontend (follows spec) |
| 5. Self-Critique | Team | Each dev reviews against SOLID + Clean Code checklists |
| 6. Security Audit | Bruno | OWASP Top 10, input validation, auth review |
| 7. Quality Assurance | Rita | Full test suite, coverage gate (80%+), ALL tests always |
| 8. Quality Gate | Marta + Eduardo + Francisca | Copy review + technical review. APPROVED or REJECTED. |
| 9. Documentation | Lucas + Paulo | Save patterns to KB, commit, final report |

---

## Project Scaffolding

Create fully configured projects with one command. Each comes with dependencies installed, integrations configured, and an Obsidian project page.

| Command | What You Get |
|---------|-------------|
| `/dev scaffold laravel <name>` | Laravel 11 + PHP 8.3 backend |
| `/dev scaffold nuxt-saas <name>` | Nuxt 3 SaaS dashboard |
| `/dev scaffold nuxt-landing <name>` | Nuxt 3 landing page |
| `/dev scaffold nuxt-docs <name>` | Nuxt 3 documentation site |
| `/dev scaffold vue-saas <name>` | Vue 3 SaaS dashboard |
| `/dev scaffold vue-landing <name>` | Vue 3 landing page |
| `/dev scaffold full-stack <name>` | Laravel backend + Nuxt frontend |
| `/dev scaffold react <name>` | React starter project |
| `/dev scaffold nextjs <name>` | Next.js starter project |

---

## Integrations (22 MCPs)

ARKA OS connects to 22 external services via MCP profiles. Integrations are automatically configured per project type.

| Profile | Includes |
|---------|----------|
| **base** | Obsidian, Context7, Playwright, Memory Bank, Sentry, GitHub Search, ClickUp, Firecrawl, Supabase |
| **laravel** | base + Laravel Boost, Serena |
| **nuxt** | base + Nuxt, Nuxt UI |
| **vue** | base + Nuxt UI |
| **react/nextjs** | base + Next DevTools |
| **ecommerce** | base + Laravel Boost, Serena, Mirakl, Shopify Dev |
| **full-stack** | base + Laravel Boost, Serena, Nuxt, Nuxt UI |
| **brand** | base + Canva |
| **comms** | base + Slack, Discord, WhatsApp, Teams |

Apply integrations to any project:

```bash
/dev mcp apply laravel    # Apply Laravel profile
/dev mcp add shopify-dev  # Add a single integration
/dev mcp status           # Show active integrations
```

---

## Plugins

ARKA OS v1.1.0 ships with two Claude Code plugins pre-installed:

### Superpowers (obra/superpowers)

Agentic skills framework providing structured workflows: brainstorming, TDD, systematic debugging, implementation plans, code review, and verification.

### Claude-Mem (thedotmack/claude-mem)

Persistent memory with vector search. Auto-captures decisions and patterns across sessions with progressive disclosure for token efficiency.

---

## AI Providers

Extensible provider system for image generation, video generation, and text completion with automatic fallback routing.

| Chain | Providers |
|-------|-----------|
| Image Generation | OpenAI → FAL → Replicate |
| Video Generation | FAL → Replicate |
| Text Completion | OpenRouter |

```bash
arka providers              # List all providers
arka providers add <id>     # Add a new provider
arka providers routing      # Show fallback chains
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `arka` | Open Claude Code with ARKA OS |
| `arka --version` | Show installed version |
| `arka update` | Pull latest and reinstall |
| `arka doctor` | Run 16 health checks |
| `arka doctor --fix` | Auto-repair common issues |
| `arka gotchas` | Show top 10 recurring errors |
| `arka test` | Run the bats test suite |
| `arka team-balance` | Show DISC team distribution |
| `arka providers` | List AI providers and models |
| `arka commands` | List all available commands |
| `arka kb queue` | Show KB job queue |
| `arka skill install <url>` | Install external skill |
| `arka skill list` | List installed skills |
| `arka skill create <name>` | Scaffold a new skill |

---

## External Skills

Extend ARKA OS with community-built skills from GitHub:

```bash
# Install a skill
arka skill install https://github.com/someone/cool-skill

# List installed skills
arka skill list

# Create your own skill
arka skill create my-skill
```

[Full external skills guide](docs/EXTERNAL-SKILLS.md) | [Skill Standard spec](docs/SKILL-STANDARD.md)

---

## Community vs Pro

| Feature | Community (Free) | Pro |
|---------|:-:|:-:|
| 9 departments | Yes | Yes |
| 22 AI team members | Yes | Yes |
| 22 integrations | Yes | Yes |
| 9 project types | Yes | Yes |
| 2 plugins (Superpowers + Claude-Mem) | Yes | Yes |
| External skills | Yes | Yes |
| 13 NON-NEGOTIABLE rules + Quality Gate | Yes | Yes |
| Growth Hacker agent | — | Yes |
| Copywriter agent | — | Yes |
| Data Analyst agent | — | Yes |
| Advanced SEO skill | — | Yes |
| Funnel Builder skill | — | Yes |
| SaaS Playbook | — | Yes |

[Learn more about Pro](https://wizardingcode.com/arka-pro)

---

## Health Checks

```bash
arka doctor        # Run 16 checks
arka doctor --fix  # Auto-repair
arka doctor --json # JSON output
```

Checks: Claude CLI, ARKA install, jq, user profile, status line, hooks, Obsidian vault, departments, personas, MCP registry, prerequisites, capabilities, agent memory, install manifest, gotchas, plugins.

---

## Testing

ARKA OS uses [bats-core](https://github.com/bats-core/bats-core) for testing:

```bash
arka test    # Run full test suite (134 tests)
bats tests/  # Run directly
```

---

## Documentation

| Guide | What It Covers |
|-------|---------------|
| [Getting Started](docs/GETTING-STARTED.md) | Installation, first run, beginner walkthrough |
| [Commands](docs/COMMANDS.md) | Complete command reference |
| [Departments](docs/DEPARTMENTS.md) | Deep dive into each department and team member |
| [Integrations](docs/INTEGRATIONS.md) | How to connect external services |
| [External Skills](docs/EXTERNAL-SKILLS.md) | Installing, managing, and creating skills |
| [Skill Standard](docs/SKILL-STANDARD.md) | Technical spec for skill developers |

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Built with purpose by [WizardingCode](https://wizardingcode.com).
