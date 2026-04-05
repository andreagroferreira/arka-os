# ArkaOS

**The Operating System for AI Agent Teams.** 62 agents across 17 departments, 250+ skills backed by 116 enterprise frameworks, 8 Python CLI tools. One install.

```
npx arkaos install
```

[![Tests](https://github.com/andreagroferreira/arka-os/actions/workflows/test.yml/badge.svg)](https://github.com/andreagroferreira/arka-os/actions) [![npm](https://img.shields.io/npm/v/arkaos)](https://www.npmjs.com/package/arkaos) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What ArkaOS Does

ArkaOS orchestrates AI agents that cover every business function. Not just code. Marketing, brand, finance, strategy, sales, operations, compliance, product management, e-commerce, communities, content, and more.

Each agent has a defined role, personality, expertise, and authority level. They work in squads, follow YAML workflows, and every output passes through a mandatory Quality Gate.

```
You: "validate my saas idea for a scheduling tool"

ArkaOS: → Routes to SaaS department
        → Tiago (SaaS Strategist) leads validation workflow
        → Market sizing, competitor analysis, business model, pricing
        → Financial viability check by Leonor (Financial Analyst)
        → Quality Gate: Marta, Eduardo, Francisca review
        → Delivers: validated report with go/no-go recommendation
```

## Install

```bash
npx arkaos install              # auto-detects runtime
npx arkaos install --runtime claude-code
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
```

Requires Node.js 18+ and Python 3.11+.

**Upgrading from v1?** Run `npx arkaos migrate`

## 17 Departments, 62 Agents

| Department | Prefix | Agents | Skills | What It Does |
|-----------|--------|--------|--------|-------------|
| Development | `/dev` | 9 | 41 | Features, APIs, architecture, security, CI/CD, RAG, agents |
| Marketing | `/mkt` | 4 | 14 | SEO, paid ads, email, growth loops, programmatic SEO |
| Brand & Design | `/brand` | 4 | 12 | Brand identity, UX/UI, design systems, naming |
| Finance | `/fin` | 3 | 8 | DCF valuation, unit economics, CISO advisory |
| Strategy | `/strat` | 3 | 9 | Five Forces, Blue Ocean, BMC, CTO/board advisory |
| E-Commerce | `/ecom` | 4 | 12 | Store optimization, CRO, RFM, pricing |
| Knowledge | `/kb` | 3 | 12 | Research, Zettelkasten, personas, Obsidian |
| Operations | `/ops` | 2 | 15 | Automation, SOPs, GDPR, ISO 27001, SOC 2, risk |
| Project Mgmt | `/pm` | 3 | 13 | Scrum, Shape Up, discovery, agile PO |
| SaaS | `/saas` | 3 | 15 | Validation, metrics, PLG, scaffolding |
| Landing Pages | `/landing` | 4 | 15 | Sales copy, funnels, offers, page generation |
| Content | `/content` | 4 | 14 | Viral design, hooks, scripts, repurposing |
| Communities | `/community` | 2 | 14 | Groups, membership, gamification |
| Sales | `/sales` | 2 | 10 | Pipeline, SPIN selling, negotiation |
| Leadership | `/lead` | 2 | 10 | Team health, OKRs, culture, hiring |
| Organization | `/org` | 1 | 10 | Org design, team topologies |
| **Quality Gate** | (auto) | 3 | — | Mandatory on every workflow. Veto power. |

## How It Works

**Just describe what you need.** ArkaOS routes it to the right squad.

```
"add user authentication"      → /dev feature
"create a brand for my app"    → /brand identity
"plan our Q3 budget"           → /fin budget
"design a sales funnel"        → /landing funnel
"are we GDPR compliant?"       → /ops gdpr-compliance
"score these headlines"        → python scripts/tools/headline_scorer.py
```

Or use explicit commands: `/dev feature "user auth"`, `/saas validate "scheduling tool"`

## Python CLI Tools

8 stdlib-only tools for quantitative analysis. No dependencies.

```bash
python scripts/tools/headline_scorer.py "10x Your Revenue" --json
python scripts/tools/seo_checker.py page.html --json
python scripts/tools/rice_prioritizer.py features.json --json
python scripts/tools/dcf_calculator.py --revenue 1000000 --growth 20 --json
python scripts/tools/tech_debt_analyzer.py src/ --json
python scripts/tools/saas_metrics.py --new-mrr 50000 --json
python scripts/tools/brand_voice_analyzer.py content.txt --json
python scripts/tools/okr_cascade.py growth --json
```

## Agent DNA

Every agent has a behavioral profile from 4 frameworks:

- **DISC** — How they communicate
- **Enneagram** — What motivates them (9 types with wings)
- **Big Five** — Personality traits (0-100 scale)
- **MBTI** — How they process information

## Quality Gate

Nothing reaches you without all three reviewers:

- **Marta** (CQO) — orchestrates and issues final verdict
- **Eduardo** — text quality: spelling, grammar, tone, AI patterns
- **Francisca** — technical quality: code, tests, UX, security

APPROVED or REJECTED. No exceptions.

## The Conclave

Personal AI advisory board with 20 real-world advisor personas (Munger, Dalio, Bezos, Naval, Jobs, Sinek, etc.). Matched to your behavioral DNA via 17-question profiling.

```
/arka conclave         # Start profiling
/arka conclave ask     # Ask all advisors
/arka conclave debate  # Advisors debate a topic
```

## Enterprise Frameworks

ArkaOS agents apply validated frameworks, not generic prompts:

| Area | Frameworks |
|------|-----------|
| Development | Clean Code, SOLID, DDD, TDD, DORA, OWASP, MITRE ATT&CK |
| Branding | Primal Branding, StoryBrand, 12 Archetypes, Positioning |
| Strategy | Porter's Five Forces, Blue Ocean, BMC, Wardley Maps, 7 Powers |
| Finance | DCF Valuation, Unit Economics, COSO ERM, ALE Risk Quantification |
| Marketing | AARRR, Growth Loops, Schwartz 5 Levels, PLG, STEPPS |
| Compliance | GDPR, ISO 27001, SOC 2, ISO 31000, ISO 9001 |
| PM | Scrum, Kanban, Shape Up, Continuous Discovery, RICE |

## Multi-Runtime

| Runtime | Status |
|---------|--------|
| Claude Code | Primary — hooks, subagents, MCP, 1M context |
| Codex CLI | Supported — subagents, sandboxed execution |
| Gemini CLI | Supported — subagents, MCP, 1M context |
| Cursor | Supported — agent mode, MCP |

## Architecture

```
User Input
  ↓
Synapse (8-layer context injection)
  ↓
Orchestrator (/do → department routing)
  ↓
Squad (YAML workflow with phases and gates)
  ↓
Quality Gate (Marta + Eduardo + Francisca)
  ↓
Output (Obsidian vault + structured deliverables)
```

Built with: Python core engine, Node.js installer, Bash hooks, YAML workflows, 1688 tests.

## Commands

```bash
npx arkaos install      # Install
npx arkaos update       # Update to latest
npx arkaos migrate      # Migrate from v1
npx arkaos doctor       # Health check
npx arkaos uninstall    # Remove
```

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). PRs welcome — all changes require review.

## License

MIT — [WizardingCode](https://wizardingcode.com)
