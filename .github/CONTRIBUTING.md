# Contributing to ArkaOS

Welcome! ArkaOS is built by humans and AI working together. Whether you're a developer, a designer, a marketer, or someone using AI tools for the first time — there's a place for you here.

This guide works for both human contributors and AI agents (Claude, Codex, Gemini, Cursor).

---

## Quick Start

```bash
# 1. Fork and clone
git clone git@github.com:YOUR-USERNAME/arka-os.git
cd arka-os

# 2. Create a branch
git checkout -b feat/your-feature

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Make your changes

# 5. Run tests
python -m pytest tests/ -q

# 6. Validate skills (if you changed any)
python scripts/skill_validator.py departments/ --summary

# 7. Commit and push
git commit -m "feat: your change description"
git push origin feat/your-feature

# 8. Open a Pull Request against master
```

---

## What Can You Contribute?

### For Everyone
- **Report bugs** — Something broken? [Open an issue](https://github.com/andreagroferreira/arka-os/issues)
- **Suggest features** — Have an idea? Start a discussion
- **Improve docs** — Typos, unclear instructions, better examples
- **Translate** — Help make ArkaOS available in more languages

### For Developers
- **New skills** — Add skills to any of the 17 departments
- **Python tools** — Build stdlib-only CLI tools for analysis
- **Dashboard** — Improve the Nuxt 4 monitoring UI
- **Core engine** — Synapse layers, workflow engine, orchestration
- **Tests** — More coverage, edge cases, integration tests

### For Non-Developers
- **Skill content** — Write better framework-backed skill instructions
- **Reference docs** — Deep knowledge documents for skills
- **Use cases** — Document real-world usage scenarios
- **Personas** — Create personas based on real industry experts

### For AI Agents
- Read `CLAUDE.md` for project structure and conventions
- Read `config/constitution.yaml` for governance rules
- Follow the SKILL.md format in `docs/SKILL-STANDARD.md`
- Run `python scripts/skill_validator.py` before submitting
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`

---

## Project Structure

```
arka-os/
├── core/               # Python engine (Synapse, workflows, agents, budget, knowledge)
├── departments/        # 17 departments × agents + skills + workflows
├── scripts/            # CLI tools + synapse bridge + knowledge indexer
├── installer/          # Node.js installer (npx arkaos install)
├── dashboard/          # Nuxt 4 + NuxtUI monitoring UI
├── config/             # Constitution, hooks, standards
├── docs/               # Documentation (9 guides)
└── tests/              # Python tests (1836+)
```

---

## How to Create a New Skill

Skills are the building blocks of ArkaOS. Each skill is a markdown file that tells an agent how to do something.

### 1. Pick a department

| Department | Prefix | Good for |
|-----------|--------|----------|
| dev | `/dev` | Coding, architecture, security, CI/CD |
| marketing | `/mkt` | SEO, campaigns, email, growth |
| brand | `/brand` | Identity, design, naming |
| finance | `/fin` | Budgets, valuation, forecasting |
| strategy | `/strat` | Analysis, planning, competitive intel |
| ops | `/ops` | SOPs, compliance, automation |
| saas | `/saas` | Validation, metrics, PLG |
| content | `/content` | Viral content, hooks, scripts |

See all 17 departments in `docs/DEPARTMENTS.md`.

### 2. Create the skill

```bash
mkdir -p departments/dev/skills/my-new-skill
```

### 3. Write the SKILL.md

```markdown
---
name: dev/my-new-skill
description: >
  What this skill does in one sentence.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Skill Title — `/dev my-new-skill`

> **Agent:** Paulo (Dev Lead) | **Framework:** Framework Name

## What It Does

Brief explanation.

## How It Works

Tables, checklists, actionable steps.

## Proactive Triggers

Surface these issues WITHOUT being asked:

- condition → what to flag
- condition → what to flag

## Output

```markdown
Expected output template
```
```

### 4. Validate

```bash
python scripts/skill_validator.py departments/dev/skills/my-new-skill
```

Target: EXCELLENT (90+/100).

### 5. Add reference docs (optional)

For complex skills, add deep knowledge in `references/`:

```
departments/dev/skills/my-new-skill/
├── SKILL.md
└── references/
    └── deep-knowledge.md
```

---

## Coding Standards

### Python
- Type hints on all functions
- Pydantic models for data structures
- pytest for tests
- stdlib-only for CLI tools (no pip deps)
- docstrings on public functions

### JavaScript/TypeScript (Dashboard)
- Nuxt 4 + NuxtUI v4
- Composition API
- TypeScript
- `UDashboardPanel` with `#header` / `#body` slots

### Skills (SKILL.md)
- 60-120 lines ideal
- Tables and checklists over prose
- One agent per skill
- Framework attribution
- 3+ proactive triggers
- Output template section

### Commits
```
feat: new feature
fix: bug fix
docs: documentation
refactor: code improvement
test: test additions
chore: maintenance
```

---

## Pull Request Process

1. **Branch from master** — `feat/`, `fix/`, `docs/`, `refactor/`, `test/`
2. **One focus per PR** — Don't mix features with bug fixes
3. **Tests must pass** — `python -m pytest tests/ -q`
4. **Skills must validate** — `python scripts/skill_validator.py departments/ --summary`
5. **Update CHANGELOG.md** for user-facing changes
6. **PR description** — Use the template. Explain what and why.

### PR Review

- All PRs require at least one review
- Direct pushes to `master` are blocked
- CI runs: Python tests (3.11/3.12/3.13), Node.js syntax, skill validation
- Be patient — maintainers will review as soon as possible

---

## Working with AI Agents

ArkaOS is designed to be used with AI coding tools. If you're contributing via Claude Code, Codex, or Cursor:

### Before You Start
```
/arka status          # Check system state
/dev research         # Research before building
```

### Constitution Rules
The constitution at `config/constitution.yaml` defines what agents can and cannot do. Key rules:
- Spec before code (spec-driven development)
- Branch isolation (no direct commits to master)
- Quality Gate (Marta, Eduardo, Francisca review everything)
- SOLID + Clean Code always

### Testing Your Changes
```bash
python -m pytest tests/ -q                    # All tests
python -m pytest tests/python/test_X.py -v    # Specific test
python scripts/skill_validator.py departments/ # Validate skills
```

---

## Community

- **Issues** — [github.com/andreagroferreira/arka-os/issues](https://github.com/andreagroferreira/arka-os/issues)
- **Discussions** — Use GitHub Discussions for ideas and questions
- **License** — MIT — use ArkaOS freely, contribute back if you can

---

## Thank You

Every contribution matters — a typo fix, a new skill, a bug report, a translation. ArkaOS is built by the community, for the community.

*ArkaOS — The Operating System for AI Agent Teams — WizardingCode*
