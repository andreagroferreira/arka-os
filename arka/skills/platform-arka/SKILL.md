---
name: arka-platform-arka
description: >
  ArkaOS platform ecosystem orchestrator. Self-managing product development for ArkaOS —
  the core WizardingCode product. Full-stack product team: Python core engine, Node.js
  installer/CLI, React dashboard, skills, agents, departments. Manages features, fixes,
  releases (semi-auto with confirmation gate), test suite (542+ pytest), self-auditing,
  and auto-evolution (detects gaps, proposes and implements improvements).
  Reports to /wiz (WizardingCode Internal) for strategic alignment.
  Use when user says "platform-arka", "arkaos dev", "arkaos feature", "arkaos release",
  "arkaos audit", "arkaos evolve", "platform", or wants to develop/improve ArkaOS itself.
---

# ArkaOS Platform — Product Development Ecosystem

Self-managing product development orchestrator for ArkaOS. **The system that evolves itself.**

## Project

| Property | Value |
|----------|-------|
| **Product** | ArkaOS |
| **Company** | WizardingCode |
| **Path** | `/Users/andreagroferreira/AIProjects/arka-os` |
| **Stack** | Python (core) + Node.js (installer/CLI) + React (dashboard) |
| **Reports to** | `/wiz` (WizardingCode Internal) |
| **Version file** | `VERSION` (also `package.json`, `pyproject.toml`) |
| **Tests** | `pytest` (542+ tests in `tests/python/`) |

## Architecture

```
core/ (Python: Synapse, workflows, agents, governance, runtime)
installer/ (Node.js CLI + adapters) · scripts/ (React dashboard + FastAPI)
departments/ (17 depts: agents, skills, workflows) · config/ · knowledge/
tests/python/ (542+ pytest)
```

## Squad — The Platform Team

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Product Owner** | `strategy-director` | Roadmap, prioritization, OKRs, reports to `/wiz` |
| **Core Engineer** | `backend-dev` | Python core — Synapse, workflows, agents, governance |
| **CLI Engineer** | `backend-dev` | Node.js installer, CLI tools, bash hooks |
| **Dashboard Engineer** | `frontend-dev` | React dashboard, FastAPI endpoints, WebSocket |
| **Skill Architect** | `architect` | Skill design, agent YAML, department structure |
| **DevOps** | `devops-eng` | npm publish, GitHub releases, CI/CD, versioning |
| **QA Engineer** | `qa-eng` | pytest suite, integration tests, regression |
| **Security Engineer** | `security-eng` | Dependency audit, OWASP, installer security |
| **Platform Analyst** | `research-analyst` | Self-analysis, gap detection, evolution proposals |

## Commands

### Standard Product Commands

| Command | Description |
|---------|-------------|
| `/platform-arka` | General — describe what you need, orchestrator routes |
| `/platform-arka status` | Project status (version, coverage, issues, releases) |
| `/platform-arka feature <desc>` | Plan and implement a new feature |
| `/platform-arka fix <desc>` | Debug and fix an issue |
| `/platform-arka test` | Run full pytest suite + report |
| `/platform-arka review` | Code review of recent changes |
| `/platform-arka docs` | Update documentation (CLAUDE.md, CONTRIBUTING, Obsidian) |

### Release Pipeline

| Command | Description |
|---------|-------------|
| `/platform-arka release <type>` | Semi-auto release: bump, changelog, commit. Pauses before push + npm publish + GitHub release |
| `/platform-arka release status` | Check latest release, npm version, GitHub tags |

### Auto-Evolution Commands

| Command | Description |
|---------|-------------|
| `/platform-arka audit` | Self-analysis: code quality, test gaps, missing skills, agents without DNA, dead code, CLAUDE.md accuracy |
| `/platform-arka evolve` | Propose improvements from audit — with approval, implements |
| `/platform-arka roadmap` | View/update roadmap, synced with `/wiz` priorities |
| `/platform-arka metrics` | Coverage, agent count, skill count, department completeness, version history |

### Skill & Agent Management

| Command | Description |
|---------|-------------|
| `/platform-arka skill create <name>` | Scaffold a new skill (SKILL.md + registration) |
| `/platform-arka skill list` | List all skills with status |
| `/platform-arka agent create <name>` | Create new agent YAML with behavioral DNA |
| `/platform-arka agent validate` | Validate all agent YAMLs (4-framework consistency) |
| `/platform-arka department <name>` | Department health check (agents, skills, workflows) |

## Orchestration

The squad executes every request through a common arc: context loading → planning → user approval → execution (branch/worktree isolation where applicable) → Quality Gate (Marta/Eduardo/Francisca, mandatory) → Obsidian documentation. Releases additionally pause at a confirmation gate before publish. Evolve and audit flows use the Platform Analyst to scan departments, agents, skills, test coverage, and code quality, then propose ranked improvements.

**See `references/workflows.md` for the full step-by-step flows** (Standard, Release, Audit, Evolve, Status, Metrics, Skill Create, Agent Create).

## Branch Strategy

| Scenario | Branch Pattern | Isolation |
|----------|---------------|-----------|
| Features | `feature/<desc>` | Worktree |
| Evolution improvements | `evolve/<desc>` | Worktree |
| Hotfixes, simple patches | Direct on `master` | None |
| Releases | From `master` | None (bump + tag + publish) |

## /wiz Integration

- ArkaOS appears in `/wiz projects` and `/wiz status` as an active internal project
- `/wiz` sets strategic priorities that `/platform-arka roadmap` reflects
- Revenue (ARKA OS Pro) tracked via `/wiz finance`; roadmap syncs against `/wiz` OKRs

## Obsidian Output

All documentation under `/Users/andreagroferreira/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/`:
`Roadmap.md`, `Releases/vX.Y.Z.md`, `Audits/YYYY-MM-DD.md`, `Evolution Log.md`, `Metrics.md`.

## References

- `references/workflows.md` — Full orchestration flows (Standard, Release, Audit, Evolve, Status, Metrics, Skill Create, Agent Create)
