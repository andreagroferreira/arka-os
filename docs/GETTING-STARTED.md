# Getting Started with ArkaOS

Install and start using ArkaOS in under 5 minutes.

## Prerequisites

- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Python 3.11+** — [python.org](https://python.org)
- **An AI coding tool** — Claude Code, Codex CLI, Gemini CLI, or Cursor

## Install

```bash
npx arkaos install
```

Auto-detects your runtime. Or specify:

```bash
npx arkaos install --runtime claude-code
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor
```

## Verify Installation

```bash
npx arkaos doctor
```

## First Use

Just describe what you need. ArkaOS routes it to the right department.

```
"fix the authentication bug"     → Dev department
"create a brand for my app"      → Brand department
"plan the Q3 budget"             → Finance department
"validate my saas idea"          → SaaS department
"write viral hooks for TikTok"   → Content department
"are we GDPR compliant?"         → Operations department
```

Or use explicit commands:

```
/dev feature "user authentication"
/brand identity "fintech startup"
/mkt seo-audit
/strat blue-ocean "AI tools market"
/saas validate "scheduling tool"
```

## Project Setup

Initialize ArkaOS in your project directory:

```bash
npx arkaos init
```

Creates `.arkaos.json` with auto-detected stack (Laravel, Nuxt, Next.js, React, Vue, Python, Go, Rust).

## Dashboard

Monitor everything through the web UI:

```bash
npx arkaos dashboard
```

Opens at http://localhost:3333 with:
- Agent browser with full behavioral DNA profiles
- Command search across 17 departments
- Token usage by department
- Task monitor
- Knowledge base management
- System health checks

## Knowledge Base

Index your Obsidian vault for semantic search:

```bash
npx arkaos index
```

Search indexed knowledge:

```bash
npx arkaos search "authentication patterns"
```

ArkaOS automatically retrieves relevant knowledge during prompts via the Synapse engine.

## Python Tools

8 CLI tools for quantitative analysis:

```bash
python scripts/tools/headline_scorer.py "10x Your Revenue" --json
python scripts/tools/seo_checker.py page.html --json
python scripts/tools/dcf_calculator.py --revenue 1000000 --growth 20 --json
python scripts/tools/tech_debt_analyzer.py src/ --json
```

## Update

```bash
npx arkaos update
```

## Migrating from v1

```bash
npx arkaos migrate
```

Backs up v1, preserves your data, installs v2. See [MIGRATION-V1-V2.md](MIGRATION-V1-V2.md).

## What's Included

- **65 agents** across 17 departments with 4-framework behavioral DNA
- **244+ skills** backed by enterprise frameworks
- **24 workflows** with mandatory quality gates
- **9-layer Synapse** context injection engine
- **Vector knowledge DB** with semantic search
- **Token budget** tracking per department
- **Dashboard** for monitoring
- **1836 tests**

## Next Steps

- Browse [COMMANDS.md](COMMANDS.md) for all available commands
- Read [DEPARTMENTS.md](DEPARTMENTS.md) to understand the 17 departments
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for how it all fits together
- Create skills with [SKILL-STANDARD.md](SKILL-STANDARD.md)
