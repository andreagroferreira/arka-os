# ArkaOS

**The Operating System for AI Agent Teams.**

106 agents. 17 departments. 250+ skills. Enterprise frameworks. Multi-runtime. One install.

```bash
npx arkaos install
```

[![npm](https://img.shields.io/npm/v/arkaos)](https://www.npmjs.com/package/arkaos) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Tests](https://img.shields.io/badge/tests-1993%20passing-brightgreen)]()

---

## Why ArkaOS

Every AI coding tool gives you **one developer agent**. ArkaOS gives you **an entire company**.

Marketing teams. Brand designers. Financial analysts. Strategy consultants. Security auditors. E-commerce specialists. Content creators. Sales negotiators. Project managers. Quality reviewers. All working together, following enterprise workflows, with mandatory quality gates.

And now, with the **Cognitive Layer** (v2.10), ArkaOS **learns from experience**. It remembers solutions across projects, critiques its own work every night, and researches updates about your tech stack while you sleep.

```
You: "add stripe subscription billing"

ArkaOS: → Routes to Development department
        → Paulo (Tech Lead) plans the feature
        → Ana (Backend) implements with TDD
        → Sofia (Security) audits for OWASP Top 10
        → Quality Gate: Marta reviews, Eduardo checks docs, Francisca verifies code
        → Delivers: tested, secure, documented implementation
```

```
You: "create a go-to-market plan for my SaaS"

ArkaOS: → Routes to Strategy + Marketing + SaaS departments
        → Tomas (Strategist) builds competitive analysis
        → Luna (Growth) designs acquisition funnels
        → Tiago (SaaS) models PLG metrics and pricing
        → Quality Gate ensures Silicon Valley-grade output
        → Delivers: complete GTM plan with financial projections
```

---

## Quick Start

### Prerequisites

- **Node.js 18+** (or Bun)
- **Python 3.11+**
- One of: [Claude Code](https://claude.ai/code), [Codex CLI](https://github.com/openai/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), or [Cursor](https://cursor.com)

### Install

```bash
npx arkaos install
```

The installer auto-detects your runtime and configures everything:
- Python dependencies (Pydantic, PyYAML, Rich, Click)
- Hook system (5 hooks for session management)
- Skills (250+ department commands)
- Cognitive Layer scheduler (Dreaming + Research)

Prefer a specific runtime?

```bash
npx arkaos install --runtime claude-code
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
```

### Update

```bash
# Step 1: Update core (terminal)
npx arkaos@latest update

# Step 2: Sync projects (inside your AI tool)
/arka update
```

### Verify

```bash
npx arkaos doctor    # Health check
```

---

## How It Works

### 1. You describe what you need

In plain language. No special syntax required.

### 2. ArkaOS routes to the right squad

The Synapse engine (8-layer context injection in <1ms) analyzes your request and routes it to the correct department. Each department has a lead agent who orchestrates specialists.

### 3. Agents execute with enterprise frameworks

Not generic prompts. Validated methodologies:

| Area | Frameworks Used |
|------|----------------|
| Development | Clean Code, SOLID, DDD, TDD, DORA, OWASP |
| Strategy | Porter's Five Forces, Blue Ocean, BMC, Wardley Maps |
| Finance | DCF Valuation, Unit Economics, COSO ERM |
| Marketing | AARRR, Growth Loops, PLG, STEPPS |
| Brand | Primal Branding, StoryBrand, 12 Archetypes |
| E-Commerce | ResearchXL, RFM, Baymard, MACH |
| Compliance | GDPR, ISO 27001, SOC 2, ISO 31000 |

### 4. Quality Gate reviews everything

Nothing reaches you without review by three agents:
- **Marta** (CQO) — orchestrates, issues final APPROVED/REJECTED
- **Eduardo** — text quality: spelling, grammar, tone, zero AI cliches
- **Francisca** — technical quality: code, tests, UX, security

### 5. Knowledge persists

Every decision, solution, and pattern is captured. The Cognitive Layer curates it overnight. Tomorrow, ArkaOS is smarter than today.

---

## 17 Departments

| Department | Prefix | Agents | What It Does |
|-----------|--------|--------|-------------|
| **Development** | `/dev` | 10 | Full-stack features, APIs, architecture, security, CI/CD |
| **Marketing** | `/mkt` | 4 | SEO, paid ads, email campaigns, growth loops |
| **Brand & Design** | `/brand` | 4 | Brand identity, UX/UI, design systems, naming |
| **Finance** | `/fin` | 3 | DCF valuation, unit economics, budgets, investor prep |
| **Strategy** | `/strat` | 3 | Market analysis, competitive intelligence, business models |
| **E-Commerce** | `/ecom` | 4 | Store optimization, CRO, pricing, RFM segmentation |
| **Knowledge** | `/kb` | 3 | Research, Zettelkasten, persona building, ingestion |
| **Operations** | `/ops` | 4 | Automation, SOPs, compliance (GDPR, ISO, SOC 2) |
| **Project Mgmt** | `/pm` | 3 | Scrum, Shape Up, discovery, roadmaps |
| **SaaS** | `/saas` | 4 | Idea validation, metrics, PLG strategy, scaffolding |
| **Landing Pages** | `/landing` | 4 | Sales copy, funnels, offers, page generation |
| **Content** | `/content` | 4 | Viral hooks, scripts, repurposing, content calendars |
| **Communities** | `/community` | 2 | Groups, membership, gamification, engagement |
| **Sales** | `/sales` | 2 | Pipeline management, SPIN selling, negotiation |
| **Leadership** | `/lead` | 2 | Team health, OKRs, culture, hiring frameworks |
| **Organization** | `/org` | 1 | Org design, team topologies, matrix structure |
| **Quality Gate** | (auto) | 3 | Mandatory review on every workflow. Veto power. |

---

## Cognitive Layer (v2.10)

ArkaOS doesn't just execute — it **learns, dreams, and researches**.

### Institutional Memory

Every solution you implement is captured and indexed. When you need authentication in a new Laravel project, ArkaOS already knows how you did it in the last three projects — with the exact pattern, configuration, and lessons learned.

- **Dual-write**: Obsidian (human-readable) + Vector DB (semantic search)
- **Cross-project**: Knowledge from ClientRetail applies to ClientFashion
- **Confidence scoring**: Patterns validated 3+ times become "validated patterns"

### Dreaming (runs at 02:00)

Every night, ArkaOS reviews the entire day:

- **Self-critique**: "Did I do this the best way? Was there a simpler approach?"
- **Pattern detection**: Promotes recurring solutions to validated patterns
- **Anti-pattern detection**: Flags repeated mistakes
- **Strategic reflection**: "Does this serve the business or just the developer?"
- **Actionable insights**: Concrete recommendations per project

When you open a project the next morning:

```
Pending reflections from Dreaming:

1. [business] Offer model — rethink
   The offers table doesn't consider volume pricing tiers.
   Shopify B2B uses min_qty + tier_price for 23% higher conversion.

2. [technical] Sync retry — improve
   Fixed backoff can cause thundering herd. Use exponential
   backoff with jitter (validated pattern from ClientRetail).

Want me to elaborate?
```

### Research (runs at 05:00)

Every morning, ArkaOS researches updates relevant to your work:

- **Stack-aware**: Laravel security patches, Nuxt 4 migration guides, Python releases
- **Domain-aware**: E-commerce trends, AI/ML updates, industry news
- **Business-aware**: Competitor moves, market opportunities, funding trends
- **Adaptive**: Infers your profile from active projects — no manual configuration

```
Intelligence Briefing — 2026-04-10

ACTION REQUIRED:
- Laravel 12.1.3 security patch — SQL injection in whereHas.
  Affects: ClientFashion, ClientCommerce. Fix: composer update laravel/framework.

OPPORTUNITIES:
- Shopify Winter '26 bulk product API — ClientCommerce sync could be 10x faster.
- Nuxt 4 RC2 migration guide published — start preparing ClientVideo.

COMPETITOR WATCH:
- CrewAI v3 launched memory layer — similar to our Cognitive Layer
  but without dual-write. ArkaOS is ahead.
```

### Cross-Platform Scheduler

The scheduler works on macOS, Linux, and Windows:

```bash
arkaos scheduler status       # Check status
arkaos scheduler run dreaming # Run manually
arkaos scheduler run research # Run manually
arkaos scheduler logs         # View logs
```

---

## Ecosystem Management

ArkaOS manages client projects as **ecosystems** — groups of related projects with dedicated squads.

```
/client_retail          → ClientRetail ecosystem (4 projects: API, frontend, admin, docs)
/client_commerce            → ClientCommerce ecosystem (supplier sync + Shopify theme)
/client_fashion      → ClientFashion (6 projects: CRM, store, API, migration...)
/edp               → EDP (3 projects: portal, API, analytics)
```

Each ecosystem gets:
- A dedicated squad with specialized roles
- Project-specific context loaded automatically when you `cd` into the project
- Overnight insights tailored to that ecosystem's domain
- Knowledge that compounds across all projects in the ecosystem

---

## The Conclave

Your personal AI advisory board. 20 real-world advisor personas — Munger, Dalio, Bezos, Naval, Jobs, Sinek, and more — matched to your behavioral DNA.

```
/arka conclave         # 17-question profiling to build your board
/arka conclave ask     # Ask all advisors a question
/arka conclave debate  # Watch advisors debate a topic
```

---

## Agent DNA

Every agent has a complete behavioral profile from 4 psychological frameworks:

| Framework | What It Defines | Example (Paulo, Tech Lead) |
|-----------|----------------|---------------------------|
| **DISC** | Communication style | D: 85, I: 60, S: 40, C: 75 |
| **Enneagram** | Core motivation | Type 5w6 (Investigator) |
| **Big Five** | Personality traits | O:88 C:92 E:55 A:65 N:22 |
| **MBTI** | Information processing | INTJ |

This isn't cosmetic — it affects how agents collaborate, what they prioritize, and how they communicate. A high-D agent pushes for speed. A high-C agent insists on thoroughness. The tension produces better outcomes.

---

## Python CLI Tools

8 standalone tools for quantitative analysis. No dependencies beyond stdlib.

```bash
python scripts/tools/headline_scorer.py "10x Your Revenue" --json
python scripts/tools/seo_checker.py page.html --json
python scripts/tools/dcf_calculator.py --revenue 1000000 --growth 20 --json
python scripts/tools/rice_prioritizer.py features.json --json
python scripts/tools/saas_metrics.py --new-mrr 50000 --json
python scripts/tools/tech_debt_analyzer.py src/ --json
python scripts/tools/brand_voice_analyzer.py content.txt --json
python scripts/tools/okr_cascade.py growth --json
```

---

## Multi-Runtime Support

| Runtime | Status | Features |
|---------|--------|----------|
| **Claude Code** | Primary | Hooks, subagents, MCP, 1M context |
| **Codex CLI** | Supported | Subagents, sandboxed execution |
| **Gemini CLI** | Supported | Subagents, MCP, 1M context |
| **Cursor** | Supported | Agent mode, MCP |

---

## Architecture

```
User Input
  │
  ▼
Synapse v2 (8-layer context injection, <1ms, cached)
  │
  ▼
Orchestrator (/do → department routing)
  │
  ▼
Squad (YAML workflow with phases and gates)
  │
  ▼
Quality Gate (Marta + Eduardo + Francisca)
  │
  ▼
Cognitive Layer (capture → dual-write → insights)
  │
  ▼
Output (Obsidian vault + structured deliverables)
```

### Core Systems

| System | Purpose |
|--------|---------|
| **Synapse v2** | 8-layer context injection (<1ms, with caching) |
| **Workflow Engine** | YAML workflows with phases, gates, parallelization |
| **Agent Schema** | 4-framework behavioral DNA with consistency validation |
| **Squad Framework** | Department squads + ad-hoc project squads (matrix) |
| **Cognitive Layer** | Memory, Dreaming, Research, Scheduler |
| **Living Specs** | Bidirectional spec/code sync |
| **Governance** | Constitution with 14 non-negotiable rules |
| **Multi-Runtime** | Claude Code, Codex, Gemini, Cursor adapters |

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Core Engine | Python 3.11+ (Pydantic, PyYAML, Rich) |
| Installer | Node.js/Bun (ESM) |
| Hooks | Bash |
| Workflows | YAML |
| Agent Definitions | YAML |
| Knowledge | Obsidian + SQLite-VSS |
| Tests | pytest (1,993 tests) |

---

## Documentation

Full documentation is available on the **[GitHub Wiki](https://github.com/andreagroferreira/arka-os/wiki)**:

- [Getting Started](https://github.com/andreagroferreira/arka-os/wiki/Getting-Started)
- [Installation Guide](https://github.com/andreagroferreira/arka-os/wiki/Installation)
- [Departments & Agents](https://github.com/andreagroferreira/arka-os/wiki/Departments)
- [Cognitive Layer](https://github.com/andreagroferreira/arka-os/wiki/Cognitive-Layer)
- [Ecosystem Management](https://github.com/andreagroferreira/arka-os/wiki/Ecosystems)
- [Configuration](https://github.com/andreagroferreira/arka-os/wiki/Configuration)
- [Creating Projects](https://github.com/andreagroferreira/arka-os/wiki/Creating-Projects)
- [Update & Sync](https://github.com/andreagroferreira/arka-os/wiki/Update-and-Sync)

---

## CLI Reference

```bash
npx arkaos install       # Fresh install (auto-detects runtime)
npx arkaos update        # Update to latest version
npx arkaos migrate       # Migrate from v1
npx arkaos doctor        # Health check
npx arkaos dashboard     # Start monitoring dashboard
npx arkaos keys          # Manage API keys
npx arkaos uninstall     # Remove ArkaOS
```

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). PRs welcome — all changes require passing the full test suite (1,993 tests) and Quality Gate review.

## License

MIT — [WizardingCode](https://wizardingcode.com)
