# 05 · Commands Reference

← [Departments](04-Departments/) · [Home](Home.md) · Next: [Cognitive Layer →](06-Cognitive-Layer.md)

Every command available in ArkaOS, in one place: the terminal installer CLI,
the in-session `/arka` system commands, the universal `/do` router, and all
16 department prefixes with representative examples.

---

## Terminal installer CLI

These commands run in your shell before or outside any AI session.

```bash
npx arkaos install                       # Fresh install (auto-detects runtime)
npx arkaos install --runtime claude-code # Install for a specific runtime
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
npx arkaos init                          # Initialize ArkaOS in the current project directory
npx arkaos@latest update                 # Update core + hooks to latest version (Step 1 of 2)
npx arkaos doctor                        # Health check — runs 9 diagnostic checks
npx arkaos dashboard                     # Start monitoring dashboard (localhost:3333)
npx arkaos keys                          # Manage API keys interactively
npx arkaos migrate                       # Migrate from v1
npx arkaos uninstall                     # Remove ArkaOS
```

---

## Two-step update

ArkaOS updates follow a two-step process. Both steps are required:

| Step | Where | Command | What it does |
|---|---|---|---|
| 1 | Terminal | `npx arkaos@latest update` | Downloads latest core, updates hooks, resets sync state |
| 2 | Inside AI session | `/arka update` | AI-powered sync of all project configs, MCP, settings, skills |

When the core version advances but the project configs have not been synced,
the `SessionStart` hook emits `[arka:update-available]` to prompt the second step.

---

## System commands (`/arka`)

In-session commands issued inside Claude Code, Codex, Gemini CLI, or Cursor.

| Command | Description |
|---|---|
| `/arka status` | System status: version, departments, agents, active projects, LLM costs (24 h), enforcement summary, and today's reorganization proposal. |
| `/arka costs [today\|week\|month\|all\|sessions]` | LLM cost visibility — aggregates telemetry by period, shows top expensive sessions. Defaults to `today`. |
| `/arka enforcement [today\|week\|month\|all]` | Flow-marker compliance — block rate, top blocked tools, top block reasons. |
| `/arka compliance [today\|week\|month\|all]` | Behavior compliance: closing marker rate, `[arka:meta]` tag rate, KB citation pass rate, sycophancy-clean rate. |
| `/arka reorganize [--since-days N]` | Reads recent KB pattern/anti-pattern/lesson artifacts (default 7 days) and generates a reorganization proposal at `~/.arkaos/reorganize-proposals/<date>.md`. Propose-only — never modifies agent YAMLs. Auto-fires on session start when today's proposal is missing. |
| `/arka standup` | Daily standup — active projects, priorities, blockers, updates. |
| `/arka monitor` | System health monitoring. |
| `/arka onboard <path>` | Onboard an existing project directory into ArkaOS. |
| `/arka conclave` | Activate the personal AI advisory board (20 advisor personas). |
| `/arka dashboard` | Open the monitoring dashboard (localhost:3333). |
| `/arka index` | (Re)index the Obsidian vault into the vector knowledge store. |
| `/arka search <query>` | Semantic search across the indexed knowledge base. |
| `/arka keys` | Manage API keys (OpenAI, Google, fal.ai). |
| `/arka personas` | Manage AI personas — create, inspect, clone to agent. |
| `/arka resume <PR_URL>` | Re-enter the Claude Code session that produced a given PR (GitHub / GitLab / Bitbucket). |
| `/arka update` | Sync all project configs after a core update (Step 2 of 2). |
| `/arka help` | List all department commands. |

---

## Universal router (`/do`)

`/do <description>` accepts plain language and routes to the correct
department command automatically. You do not need to memorize prefixes.

```
/do "fix the checkout bug"              --> /dev debug
/do "create a brand for my fintech"     --> /brand identity-system
/do "plan the Q3 budget"                --> /fin budget-plan
/do "validate my SaaS idea"             --> /saas validate-idea
/do "write viral hooks for TikTok"      --> /content hook-write
/do "are we GDPR compliant?"            --> /ops gdpr-compliance
/do "plan the next sprint"              --> /pm sprint-plan
/do "design the landing page copy"      --> /landing copy-framework
/do "set up the Discord community"      --> /community platform-setup
```

### Routing logic

1. Explicit `/prefix` — routes directly to the department.
2. Natural language — Synapse L1 (keyword detection) + L5 (command hints) + hook context tags.
3. Single match — announces and executes. Multiple plausible matches — shows top 3 and asks. Fully ambiguous — asks which department.
4. Code-modifying requests — previews the change and asks for confirmation. Non-code requests — auto-executes.

---

## Department commands

Every department has a prefix. Use the prefix with a skill name, or describe
what you need in plain language and let `/do` route it.

### `/dev` — Development (Paulo, Tech Lead)

```bash
/dev feature "user authentication with OAuth2"
/dev code-review
/dev api-design "REST API for order management"
/dev security-audit
/dev scaffold laravel "my-new-app"
/dev tech-debt
/dev ci-cd-pipeline
/dev db-design "multi-tenant SaaS with teams"
/dev architecture-design "microservices vs monolith"
/dev debug "payments failing after Stripe webhook"
```

### `/mkt` — Marketing (Luna, Marketing Lead)

```bash
/mkt seo-audit
/mkt email-sequence "B2B SaaS launching to CTOs, $299/mo"
/mkt growth-loop "freemium developer tool"
/mkt paid-campaign "LinkedIn ads targeting CFOs, $5K budget"
/mkt calendar-plan "Q3 2026, developer audience, weekly cadence"
/mkt competitor-analysis "Notion vs Coda vs Slite"
/mkt programmatic-seo "template pages for 500 city landing pages"
/mkt ab-test "pricing page hero section"
```

### `/brand` — Brand & Design (Valentina, Creative Director)

```bash
/brand identity-system "fintech startup for Gen Z"
/brand colors "premium, trustworthy, modern"
/brand archetype-finder
/brand voice-guide "professional but approachable"
/brand logo-brief "AI-powered fitness app"
/brand ux-audit
/brand design-system "React component library"
```

### `/fin` — Finance (Helena, CFO)

```bash
/fin valuation-model "SaaS company, $2M ARR, 40% growth"
/fin budget-plan "mobile app development, 6-month timeline"
/fin unit-economics "CAC $120, LTV $840, payback 4 months"
/fin financial-model "Series A, $5M raise, 18-month runway"
/fin cashflow-forecast "next 12 months, base/bull/bear"
/fin pitch-deck "seed round, pre-revenue, AI healthcare"
```

### `/strat` — Strategy (Tomas, Strategy Director)

```bash
/strat blue-ocean "AI writing tools market"
/strat five-forces "food delivery industry in Portugal"
/strat bmc "marketplace connecting freelance designers with startups"
/strat brainstorm "how to differentiate in crowded CRM market"
/strat competitor-intelligence "Shopify vs WooCommerce vs BigCommerce"
```

### `/ecom` — E-Commerce (Ricardo, E-Commerce Lead)

```bash
/ecom store-audit "https://mystore.com"
/ecom pricing-strategy "subscription boxes, $29-89 range"
/ecom product-listing "running shoes, targeting marathon runners"
/ecom rfm-analysis
```

### `/kb` — Knowledge (Clara, Knowledge Lead)

```bash
/kb research "state of AI agents in 2026"
/kb persona-build "Alex Hormozi" --sources youtube,books
/kb learn "https://youtube.com/watch?v=..."
/kb zettelkasten "machine learning fundamentals"
```

### `/ops` — Operations (Daniel, Ops Lead)

```bash
/ops sop-create "employee onboarding process"
/ops gdpr-compliance
/ops iso27001
/ops soc2-readiness
/ops risk-assessment "cloud migration project"
/ops automate "invoice processing workflow"
```

### `/pm` — Project Management (Carolina, PM Director)

```bash
/pm sprint-plan "authentication epic, 2-week sprint"
/pm roadmap-build "Q3-Q4 2026, 3 themes"
/pm story-write "as a user, I want to export data as CSV"
/pm discovery "customer interview insights from last 10 calls"
/pm shape-up "redesign the billing page"
```

### `/saas` — SaaS (Tiago, SaaS Strategist)

```bash
/saas validate-idea "AI meeting summarizer, $15/mo"
/saas metrics-dashboard
/saas plg-setup "developer tool with free tier"
/saas churn-analysis
/saas gtm-strategy "B2B SaaS for HR teams, $99/mo"
/saas saas-scaffold "Nuxt 4 + Supabase + Stripe"
```

### `/landing` — Landing Pages (Ines, Landing Lead)

```bash
/landing copy-framework "developer productivity tool, $19/mo"
/landing funnel-design "webinar funnel for B2B SaaS"
/landing grand-slam-offer "fitness coaching program"
/landing vsl-script "online course, $497"
/landing page-optimize "current conversion rate 2.1%"
```

### `/content` — Content (Rafael, Content Strategist)

```bash
/content hook-write "productivity tips for developers"
/content viral-design "tech startup brand on TikTok"
/content youtube-script "10 Laravel tips most developers don't know"
/content repurpose "1-hour podcast episode"
/content content-os "weekly publishing cadence, 3 platforms"
```

### `/community` — Communities (Beatriz, Community Strategist)

```bash
/community platform-setup "Discord community for 500 developers"
/community growth-plan "paid membership, target 1000 members by Q4"
/community gamification "points, badges, leaderboard for learning platform"
/community membership-model "3-tier, $29/$99/$299"
```

### `/sales` — Sales (Miguel, Sales Director)

```bash
/sales pipeline-manage
/sales spin-sell "enterprise SaaS deal, $50K ACV"
/sales negotiate-prep "contract renewal, client wants 30% discount"
/sales cold-outreach "targeting VP Engineering at Series B startups"
```

### `/lead` — Leadership (Rodrigo, Leadership Lead)

```bash
/lead okr-set "company-level growth OKRs for Q3"
/lead team-health
/lead hiring-plan "engineering team, 5 hires in 6 months"
/lead culture-playbook "remote-first startup, 20 people"
```

### `/org` — Organization (Sofia, COO)

```bash
/org design "scaling from 20 to 50 people"
/org team-topology "platform team vs stream-aligned teams"
/org compensation "engineering levels and bands"
```

---

## Department routing table

| Prefix | Lead | Department |
|---|---|---|
| `/dev` | Paulo | Development |
| `/mkt` | Luna | Marketing |
| `/brand` | Valentina | Brand & Design |
| `/fin` | Helena | Finance |
| `/strat` | Tomas | Strategy |
| `/ecom` | Ricardo | E-Commerce |
| `/kb` | Clara | Knowledge |
| `/ops` | Daniel | Operations |
| `/pm` | Carolina | Project Management |
| `/saas` | Tiago | SaaS |
| `/landing` | Ines | Landing Pages |
| `/content` | Rafael | Content |
| `/community` | Beatriz | Communities |
| `/sales` | Miguel | Sales |
| `/lead` | Rodrigo | Leadership |
| `/org` | Sofia | Organization |

---

Related: [08 · Multi-Runtime](08-Multi-Runtime.md) (how commands reach each runtime),
[16 · Configuration](16-Configuration.md) (feature flags that affect command routing).
