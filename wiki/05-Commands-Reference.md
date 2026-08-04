# 05 · Commands Reference

← [Departments](04-Departments/) · [Home](Home.md) · Next: [Cognitive Layer →](06-Cognitive-Layer.md)

Every command available in ArkaOS, in one place: the terminal installer CLI,
the in-session `/arka` system commands, the universal `/do` router, and all
16 department prefixes with representative examples. In total: **299 commands**
(276 department skills + 22 `/arka` system commands).

---

## Terminal installer CLI

These commands run in your shell before or outside any AI session.

```bash
npx arkaos install                       # Fresh install (auto-detects runtime)
npx arkaos install --runtime claude-code # Install for a specific runtime
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
npx arkaos install --runtime opencode
npx arkaos init                          # Initialize ArkaOS in the current project directory
npx arkaos@latest update                 # Update core + hooks to latest version (Step 1 of 2)
npx arkaos doctor                        # Health check — the canonical doctor (venv, hooks, fastpath, security advisory)
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

In-session commands issued inside any supported runtime (Claude Code, Codex,
Gemini CLI, Cursor, OpenCode, Zed/Copilot).

| Command | Description |
|---|---|
| `/arka status` | System status: version, departments, agents, active projects, LLM costs (24 h), enforcement (24 h), MCP usage (24 h), model routing, and today's reorganization proposal. |
| `/arka costs [period]` | LLM cost visibility — telemetry by day/week/month/all, top expensive sessions, cache hit rate. |
| `/arka enforcement [period]` | Flow-marker compliance — block rate, top blocked tools, top block reasons. |
| `/arka mcps [period]` | MCP usage — total calls, servers in use, top servers and tools. |
| `/arka compliance [period]` | Behavior compliance: closing-marker rate, `[arka:meta]` tag rate, KB citation pass rate, sycophancy-clean rate. |
| `/arka reorganize [--since-days N]` | Dreaming → agent reorganizer: aggregates recent KB pattern/anti-pattern/lesson artifacts into a proposal. Propose-only. Auto-fires on session start. |
| `/arka evolve [--min-projects N] [--min-confidence X]` | Instinct evolution: ingests cross-project signals into deterministic instincts and writes a promotion proposal. Propose-only. |
| `/arka standup` | Daily standup — active projects, priorities, blockers, updates. |
| `/arka monitor` | System health monitoring. |
| `/arka onboard <path>` | Onboard an existing project directory into ArkaOS. |
| `/arka help` | List all department commands. |
| `/arka setup` | Interactive profile setup (name, company, role, objectives). |
| `/arka conclave` | Activate the personal AI advisory board (20 advisor personas). |
| `/arka dashboard` | Open the monitoring dashboard (localhost:3333). |
| `/arka index` | (Re)index the Obsidian vault into the vector knowledge store. |
| `/arka search <query>` | Semantic search across the indexed knowledge base. |
| `/arka keys` | Manage API keys (OpenAI, Google, fal.ai). |
| `/arka personas` | Manage AI personas — create, inspect, clone to agent. |
| `/arka resume <PR_URL>` | Re-enter the session that produced a given PR (GitHub / GitLab / Bitbucket). |
| `/arka refine <rough idea>` | Turn a vague or domain-unfamiliar ask into a precise English prompt (auto-suggested on vague requests). |
| `/arka recipes [list\|show\|apply] <slug>` | Reuse validated, QG-approved feature builds. Synapse auto-surfaces matches. |
| `/arka research <topic>` | Fan-out research: 5 parallel research subagents, synthesised into a cited KB note. |
| `/arka update` | Sync all project configs after a core update (Step 2 of 2). |

Other `/arka` meta skills (dispatchable as `/arka <skill> <prompt>`):
`forge` (multi-agent planning), `fusion` (model-fabric advisor),
`dreams` (nightly insight review), `checkpoint` (inter-agent checkpoints),
`design-ops` (design tokens, WCAG audits, shadcn), `refine`, `recipes`,
`research`, `costs`, `conclave`, `human-writing` (the writing gate),
and `bootstrap-agent` (spawn new specialist agents).

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
/do "set up the Discord community"      --> /community platform-select
```

### Routing logic

1. Explicit `/prefix` — routes directly to the department.
2. Natural language — Synapse L1 (keyword detection) + L5 (command hints) + hook context tags.
3. Single match — announces and executes. Multiple plausible matches — shows top 3 and asks. Fully ambiguous — asks which department.
4. Vague or domain-unfamiliar requests — routed to `/arka refine` first.
5. Code-modifying requests — previews the change and asks for confirmation. Non-code requests — auto-executes.

---

## Department commands

Every department has a prefix. Use the prefix with a skill name, or describe
what you need in plain language and let `/do` route it. Examples below use
real skills from each department's pack.

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
/dev tdd-cycle
/dev spec "export users to CSV"
/dev build-fix
/dev incident "production outage on payments"
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
/mkt ad-creative "headline variants for launch ads"
/mkt ai-seo "make the docs page quotable by LLMs"
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
/brand positioning-statement "product analytics for SMBs"
```

### `/fin` — Finance (Helena, CFO)

```bash
/fin valuation-model "SaaS company, $2M ARR, 40% growth"
/fin budget-plan "mobile app development, 6-month timeline"
/fin unit-economics "CAC $120, LTV $840, payback 4 months"
/fin financial-model "Series A, $5M raise, 18-month runway"
/fin cashflow-forecast "next 12 months, base/bull/bear"
/fin pitch-deck "seed round, pre-revenue, AI healthcare"
/fin scenario-analysis "base/optimistic/pessimistic"
```

### `/strat` — Strategy (Tomas, Strategy Director)

```bash
/strat blue-ocean "AI writing tools market"
/strat five-forces "food delivery industry in Portugal"
/strat bmc "marketplace connecting freelance designers with startups"
/strat scenario-plan "interest-rate shocks on subscription revenue"
/strat moat-analysis "7 Powers for our analytics product"
```

### `/ecom` — E-Commerce (Ricardo, E-Commerce Lead)

```bash
/ecom store-audit "https://mystore.com"
/ecom pricing-strategy "subscription boxes, $29-89 range"
/ecom product-launch "running shoes, targeting marathon runners"
/ecom rfm-segment
/ecom cro-optimize "checkout page"
/ecom cart-recovery "3-email sequence"
```

### `/kb` — Knowledge (Clara, Knowledge Lead)

```bash
/kb research-plan "state of AI agents in 2026"
/kb persona-build "Alex Hormozi" --sources youtube,books
/kb learn-content "https://youtube.com/watch?v=..."
/kb zettelkasten-process "machine learning fundamentals"
/kb search-kb "Laravel auth best practices"
/kb doc-extraction "extract tables from this PDF"
```

### `/ops` — Operations (Daniel, Ops Lead)

```bash
/ops sop-create "employee onboarding process"
/ops gdpr-compliance
/ops iso27001
/ops soc2-compliance
/ops risk-management "cloud migration project"
/ops workflow-automate "invoice processing workflow"
/ops n8n-flow "sync CRM to spreadsheet daily"
/ops terminal-ops "run and verify this deployment script"
/ops github-ops "open a PR and merge when green"
```

### `/pm` — Project Management (Carolina, PM Director)

```bash
/pm sprint-plan "authentication epic, 2-week sprint"
/pm roadmap-build "Q3-Q4 2026, 3 themes"
/pm story-write "as a user, I want to export data as CSV"
/pm discovery-plan "customer interview insights from last 10 calls"
/pm shape-pitch "redesign the billing page"
/pm epic-coordination "break the onboarding epic into issues"
```

### `/saas` — SaaS (Tiago, SaaS Strategist)

```bash
/saas validate-idea "AI meeting summarizer, $15/mo"
/saas metrics-dashboard
/saas plg-setup "developer tool with free tier"
/saas churn-analysis
/saas gtm-strategy "B2B SaaS for HR teams, $99/mo"
/saas saas-scaffold "Nuxt 4 + Supabase + Stripe"
/saas pricing-strategy "usage-based vs seat-based"
/saas voc-loop "close the loop on NPS detractors"
```

### `/landing` — Landing Pages (Ines, Landing Lead)

```bash
/landing copy-framework "developer productivity tool, $19/mo"
/landing funnel-design "webinar funnel for B2B SaaS"
/landing offer-create "fitness coaching program"
/landing optimize-page "current conversion rate 2.1%"
/landing headline-write "5 variants for the hero"
/landing lead-magnet "checklist for the free tier"
/landing popup-design "exit-intent for the blog"
```

### `/content` — Content (Rafael, Content Strategist)

```bash
/content hook-write "productivity tips for developers"
/content viral-design "tech startup brand on TikTok"
/content script-structure "10 Laravel tips most developers don't know"
/content repurpose-plan "1-hour podcast episode"
/content content-system "weekly publishing cadence, 3 platforms"
/content youtube-strategy "channel positioning for a docs channel"
/content trend-hunt "what's trending in AI agents"
```

### `/community` — Communities (Beatriz, Community Strategist)

```bash
/community platform-select "Discord vs Skool for 500 developers"
/community growth-plan "paid membership, target 1000 members by Q4"
/community gamification-design "points, badges, leaderboard for learning platform"
/community monetize-plan "3-tier, $29/$99/$299"
/community onboarding-flow "first-7-days activation"
/community moderation "rules and escalation paths"
```

### `/sales` — Sales (Miguel, Sales Director)

```bash
/sales pipeline-manage
/sales spin-sell "enterprise SaaS deal, $50K ACV"
/sales negotiate-plan "contract renewal, client wants 30% discount"
/sales prospecting "B2B SaaS prospects in Portugal"
/sales proposal-write "outcome-based proposal for Q3"
/sales revops "lead scoring and routing"
```

### `/lead` — Leadership (Rodrigo, Leadership Lead)

```bash
/lead okr-define "company-level growth OKRs for Q3"
/lead team-health
/lead hiring-plan "engineering team, 5 hires in 6 months"
/lead culture-audit "remote-first startup, 20 people"
/lead feedback-give "structure the mid-year review"
```

### `/org` — Organization (Sofia, COO)

```bash
/org org-design "scaling from 20 to 50 people"
/org team-assess "platform team vs stream-aligned teams"
/org compensation-plan "engineering levels and bands"
/org decision-framework "who decides what"
/org okr-cadence "quarterly + weekly check-ins"
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

The Quality Gate (Marta + Eduardo + Francisca) has no prefix — it runs
automatically on every workflow.

---

Related: [08 · Multi-Runtime](08-Multi-Runtime.md) (how commands reach each runtime),
[16 · Configuration](16-Configuration.md) (feature flags that affect command routing).
