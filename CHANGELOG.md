# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.2] - 2026-04-05

### Added
- Orchestration protocol with 4 coordination patterns (Solo Sprint, Domain Deep-Dive, Multi-Agent Handoff, Skill Chain)
- Communication standard (bottom-line-first, confidence tagging HIGH/MEDIUM/LOW)
- Token budget system (tier-based limits, per-task max, approval threshold, persistence)
- Obsidian vault writer (frontmatter, template vars, workflow integration)
- BUDGET_CHECK gate type in workflow engine

### Changed
- Pro manifest updated with accurate v2 baseline and new Pro items
- Removed v1 pro-manifest.json

## [2.0.1] - 2026-04-05

### Added
- 8 stdlib-only Python CLI tools (brand voice analyzer, SEO checker, headline scorer, RICE prioritizer, OKR cascade, DCF calculator, SaaS metrics, tech debt analyzer)
- 14 reference docs for deep knowledge separation (OWASP, MITRE ATT&CK, SLO design, chunking strategies, etc.)
- 6 compliance skills (GDPR, ISO 27001, SOC 2, risk management, quality management, security compliance)
- `npx arkaos migrate` command for v1 to v2 migration
- `.npmignore` for clean npm publishes
- CHANGELOG, CONTRIBUTING.md, PR template
- Branch protection on master (PRs required)
- Release workflow (manual dispatch → version bump → GitHub Release → npm publish)
- Skill validation CI step

### Fixed
- Version now read dynamically from package.json (no hardcoded strings)
- `npx arkaos update` properly checks npm and reinstalls
- Skill validator exits 0 on warnings, only 2 on failures

### Removed
- Legacy v1 directories (mcps/, projects/, skill-template/)
- 44 `__pycache__` files from npm package (449KB → 346KB)

## [2.0.0] - 2026-04-05

First stable release. See 2.0.0-alpha.1 for full feature list.

## [2.0.0-alpha.1] - 2026-04-05

### Added
- Complete rewrite as "The Operating System for AI Agent Teams"
- 62 agents across 17 departments with 4-framework behavioral DNA (DISC, Enneagram, Big Five, MBTI)
- 238 skills backed by enterprise frameworks (OWASP, DORA, Blue Ocean, AARRR, etc.)
- 24 YAML workflows (enterprise, focused, specialist) with mandatory quality gates
- The Conclave — personal AI advisory board with 20 real-world advisor personas
- Multi-runtime support: Claude Code, Codex CLI, Gemini CLI, Cursor
- Python core engine with Pydantic models and YAML-driven configuration
- Node.js installer (`npx arkaos install`) with doctor, update, uninstall
- Skill validator CLI tool (`scripts/skill_validator.py`)
- 28 skills imported from claude-skills (agent-design, rag-architect, incident, observability, red-team, etc.)
- Proactive triggers pattern on imported skills
- Synapse v2 (8-layer context injection)
- Living Specs engine (bidirectional spec/code sync)
- Squad framework (department + ad-hoc project squads)
- Governance engine (constitution, quality gates, audit trails)
- Background task system
- 1664 tests (pytest)

### Changed
- Repositioned from Bash-based CLI to Python core engine
- Expanded from 9 to 17 departments
- Expanded from 22 to 62 agents
- Agent definitions now in YAML with full behavioral profiles
- Workflows now declarative YAML with phases, gates, and parallelization

### Removed
- Legacy Bash-only architecture
- Single-runtime (Claude Code only) limitation

## [1.x] - Previous

Legacy ArkaOS v1 — Bash-based AI company operating system with 22 agents, 9 departments, 135 commands.
