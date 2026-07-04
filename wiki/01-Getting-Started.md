# 01 · Getting Started

← [Wiki Home](Home.md) · Next: [Core Concepts →](02-Core-Concepts.md)

ArkaOS is an operating system for AI agent teams. 82 agents across 17
departments handle everything from writing code to building brands to planning
finances. You talk in plain language; ArkaOS routes to the right team.

This guide gets you running in 5 minutes, with real examples for developers,
marketers, and founders.

---

## Prerequisites

- **Node.js 18+** (or Bun)
- **Python 3.11+**
- One AI runtime: [Claude Code](https://claude.ai/code), [Codex CLI](https://github.com/openai/codex),
  [Gemini CLI](https://github.com/google-gemini/gemini-cli), or [Cursor](https://cursor.com)

## Install in 3 steps

### Step 1 — Install

```bash
npx arkaos install
```

ArkaOS auto-detects your runtime. To force one:

```bash
npx arkaos install --runtime claude-code   # or codex | gemini | cursor
```

The installer configures Python dependencies, the 5-hook system, all skills,
and the Cognitive Layer scheduler.

### Step 2 — Verify

```bash
npx arkaos doctor
```

Expected output:

```
[PASS] Python 3.11+ found (3.12.4)
[PASS] Node.js 18+ found (20.11.0)
[PASS] ArkaOS installed at ~/.arkaos
[PASS] Hooks configured for claude-code
[PASS] Synapse engine responsive (~84ms cold)
[PASS] Knowledge DB initialized
[PASS] 82 agents loaded
[PASS] 267 skills validated
All checks passed.
```

### Step 3 — API keys (optional)

Only needed for knowledge-base features (YouTube transcription, embeddings):

```bash
npx arkaos keys set OPENAI_API_KEY sk-proj-...
npx arkaos keys set ANTHROPIC_API_KEY sk-ant-...
```

Keys are stored at `~/.arkaos/keys.json` with owner-only (600) file
permissions. ArkaOS never sends keys anywhere beyond the providers you
configure.

---

## Your first session

You don't memorize commands. You describe what you need, and the `/do`
orchestrator routes it. (You *can* use explicit prefixes like `/dev` or `/mkt`
when you want to be specific — see [Commands Reference](05-Commands-Reference.md).)

### As a developer — fixing a bug

Open your terminal in a Laravel project and type:

```
The login form throws a 500 error when the email field is empty.
Fix this and add proper validation.
```

ArkaOS detects a development task. Synapse injects your project context
(Laravel, PHP version, branch, recent files). Paulo, the Tech Lead, takes over:

```
[arka:routing] dev -> Paulo
Paulo (Tech Lead) -> Andre (Senior Backend Dev)

Plan:
1. Add StoreLoginRequest with email/password validation rules
2. Update LoginController to use the Form Request
3. Add JSON error formatting
4. Write a feature test for the empty-email case

Proceed? [Y/n]
```

You confirm. The backend specialist writes the fix with TDD, the suite runs,
and the Quality Gate reviews it before you see the result.

### As a marketer — a launch sequence

```
/mkt email-sequence "SaaS project-management tool launching next month,
targeting startup founders, $29/month"
```

Luna (Marketing Lead) builds a 6-email launch sequence (Brunson + AIDA) with
subject-line variants, preview text, body copy, and CTAs. Output lands in your
Obsidian vault at `Marketing/Email-Sequences/…`, ready to paste into your
email platform.

### As a founder — validating an idea

```
/saas validate-idea "An AI tool that generates unit tests from code
comments. $19/mo for indie devs, $99/mo for teams."
```

Tiago (SaaS Strategist) runs a 5-point validation: market sizing (TAM/SAM/SOM),
competitor analysis, unit economics, technical feasibility, and a go-to-market
fit score — ending with a concrete recommendation.

---

## Set up the dashboard (optional)

```bash
npx arkaos dashboard
```

Opens at **http://localhost:3333** (FastAPI backend on 3334). Eight pages:
Overview, Agents (full behavioral DNA), Commands, Budget, Tasks, Knowledge,
Personas, Health.

## Index your knowledge base (optional)

```bash
npx arkaos index                       # index your Obsidian vault
npx arkaos search "auth best practices"
```

Agents search your knowledge automatically during tasks via Synapse — you
rarely search by hand. See [Knowledge Base](09-Knowledge-Base.md) for ingesting
YouTube, PDFs, web pages, and audio.

## Initialize a project

```bash
cd your-project
npx arkaos init
```

Auto-detects your stack and writes `.arkaos.json`, which feeds Synapse so
agents always know your project context.

---

## Updating

```bash
npx arkaos update    # step 1: core + hooks (terminal)
/arka update         # step 2: sync project configs (inside your AI tool)
```

Your configuration and knowledge base are preserved. See
[Configuration](16-Configuration.md) for details.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Synapse engine not responsive" | `cd ~/.arkaos && pip install -r requirements.txt && npx arkaos doctor` |
| "No agents loaded" | `npx arkaos install --force` |
| "Hook not firing" | Check `~/.claude/settings.json` references `user-prompt-submit-v2.sh` |
| "Knowledge search returns nothing" | Run `npx arkaos index` first |
| Dashboard won't start | Free ports 3333/3334: `lsof -i :3333` |

---

## What you get

| Component | Count |
|---|---|
| Agents | 82 across 17 departments |
| Skills | 267, backed by enterprise frameworks |
| Synapse layers | 12 for context injection |
| Dashboard pages | 8 |
| Python CLI tools | 8 for quantitative analysis |
| Tests | 4,500+ (pytest) |

## Next steps

- [Core Concepts](02-Core-Concepts.md) — understand squads, agents, and the constitution
- [The Evidence Flow (4 Gates)](03-The-13-Phase-Flow.md) — how a request is handled end to end
- [Commands Reference](05-Commands-Reference.md) — every command with examples
- [Departments](04-Departments/) — what each team does and when to use it
