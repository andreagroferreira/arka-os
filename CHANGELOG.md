# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
