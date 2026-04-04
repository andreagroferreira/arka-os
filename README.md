# ArkaOS

**The Operating System for AI Agent Teams.** 56 specialized agents across 16 departments, backed by 116 enterprise frameworks. One install. Full company capability.

```
npx arkaos install
```

## What ArkaOS Does

ArkaOS orchestrates AI agents that cover every business function. Not just code. Marketing, brand, finance, strategy, sales, operations, product management, e-commerce, communities, content, and more.

Each agent has a defined role, personality, expertise, and authority level. They work in squads, follow structured workflows, and every output passes through a mandatory Quality Gate before reaching you.

```
You: "validate my saas idea for a scheduling tool"
ArkaOS: → Routes to SaaS department
        → Tiago (SaaS Strategist) leads validation workflow
        → Market sizing, competitor analysis, business model, pricing, MVP scope
        → Financial viability check by Leonor (Financial Analyst)
        → Quality Gate: Marta, Eduardo, Francisca review
        → Delivers: validated report with go/no-go recommendation
```

## Install

```bash
# Auto-detects your AI runtime
npx arkaos install

# Or specify the runtime
npx arkaos install --runtime claude-code
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
```

Requires: Node.js 18+ and Python 3.11+

## 16 Departments, 56 Agents

| Department | Prefix | Agents | What It Does |
|-----------|--------|--------|-------------|
| Development | `/dev` | 9 | Features, APIs, architecture, security, CI/CD, testing |
| Marketing | `/mkt` | 4 | SEO, paid ads, content, email, growth loops |
| Brand & Design | `/brand` | 4 | Brand identity, UX/UI, design systems, naming |
| Finance | `/fin` | 3 | Financial models, valuation, fundraising, unit economics |
| Strategy | `/strat` | 3 | Five Forces, Blue Ocean, BMC, competitive intelligence |
| E-Commerce | `/ecom` | 4 | Store optimization, CRO, RFM, pricing, marketplace |
| Knowledge | `/kb` | 3 | Research, Zettelkasten, personas, Obsidian curation |
| Operations | `/ops` | 2 | Automation (n8n, Zapier), SOPs, bottleneck analysis |
| Project Mgmt | `/pm` | 3 | Scrum, Kanban, Shape Up, discovery, roadmaps |
| SaaS | `/saas` | 3 | Validation, metrics, PLG, pricing, customer success |
| Landing Pages | `/landing` | 4 | Sales copy, funnels, offers, launches, affiliates |
| Content | `/content` | 4 | Viral design, hooks, scripts, repurposing (1 to 30+) |
| Communities | `/community` | 2 | Telegram, Discord, Skool groups, membership monetization |
| Sales | `/sales` | 2 | Pipeline, proposals, SPIN selling, negotiation |
| Leadership | `/lead` | 2 | Team health, hiring, feedback, OKRs, culture |
| Organization | `/org` | 1 | Org design, team topologies, scaling operations |
| **Quality Gate** | (auto) | 3 | Mandatory review on every workflow. Veto power. |

## How It Works

**Just describe what you need.** ArkaOS routes it to the right squad.

```
"add user authentication"     → /dev feature
"create a brand for my app"   → /brand identity
"plan our Q3 budget"          → /fin budget
"design a sales funnel"       → /landing funnel
"grow my Discord community"   → /community grow
"write viral hooks for TikTok"→ /content hook
```

Or use explicit commands: `/dev feature "user auth"`, `/saas validate "scheduling tool"`, `/strat blue-ocean "AI tools market"`

## Agent DNA

Every agent has a complete behavioral profile built from 4 frameworks:

- **DISC** — How they communicate (Driver, Inspirer, Supporter, Analyst)
- **Enneagram** — What motivates them (9 types with wings)
- **Big Five** — Personality traits on a 0-100 scale
- **MBTI** — How they process information (16 types, cognitive functions)

This creates agents with consistent, realistic personalities that communicate differently based on their role and the situation.

## Quality Gate

Nothing reaches you without approval from all three reviewers:

- **Marta** (CQO) orchestrates the review and issues the final verdict
- **Eduardo** reviews all text: spelling, grammar, tone, AI patterns
- **Francisca** reviews all technical output: code quality, tests, UX, security

Binary verdict: APPROVED or REJECTED. No exceptions. No soft approvals.

## Enterprise Frameworks

ArkaOS agents don't improvise. They apply validated frameworks:

| Area | Frameworks |
|------|-----------|
| Development | Clean Code, SOLID, DDD, TDD, DORA Metrics, OWASP Top 10 |
| Branding | Primal Branding, StoryBrand, 12 Archetypes, Positioning |
| Strategy | Porter's Five Forces, Blue Ocean, BMC, Wardley Maps, 7 Powers |
| Finance | DCF Valuation, Unit Economics, COSO ERM, FP&A, Venture Deals |
| Marketing | AARRR, Growth Loops, Schwartz 5 Levels, PLG, STEPPS |
| GTM/Launch | Hormozi Grand Slam, Value Ladder, PLF, Crossing the Chasm |
| Organization | Team Topologies, Five Dysfunctions, OKRs, Netflix Culture |
| PM | Scrum, Kanban, Shape Up, Continuous Discovery, Monte Carlo |

## Multi-Runtime

ArkaOS works with any AI coding tool:

| Runtime | Status | Features |
|---------|--------|----------|
| Claude Code | Primary | Hooks, subagents, MCP, 1M context |
| Codex CLI | Supported | Subagents, sandboxed execution |
| Gemini CLI | Supported | Subagents, MCP, 1M context |
| Cursor | Supported | Agent mode, MCP |

## Architecture

```
User Input
  ↓
Synapse (8-layer context injection, <1ms)
  ↓
Orchestrator (/do → department routing)
  ↓
Squad (YAML workflow with phases and gates)
  ↓
Quality Gate (Marta + Eduardo + Francisca)
  ↓
Obsidian (all output saved to vault)
```

Built with: Python core engine, Node.js installer, Bash hooks, YAML workflows.

## Community & Pro

**Community Edition** (this repo): 56 agents, 16 departments, ~216 commands, full workflow engine.

**Pro** (coming soon): Additional agents, premium skills, knowledge packs, priority support.

## License

MIT

---

**ArkaOS** — WizardingCode
