# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.17.0] - 2026-04-12

### Added

- **Project Runtime Sync umbrella** — `/arka update` now brings all 81
  projects to the current core behavior, not just MCP configs.
  - **Content Sync** (Sub-feature A): per-project CLAUDE.md, rules, hooks,
    and constitution excerpt synced via intelligent managed-region merge.
    HTML-comment markers delimit core-owned regions; project-authored
    content outside markers is preserved forever. Stack overlays
    (`laravel`, `nuxt`, `python`, `node`) append stack-specific conventions
    inside the managed block.
  - **MCP Optimizer** (Sub-feature B): hybrid policy + AI fallback decides
    which MCPs load active vs deferred per project. Policy registry in
    `config/mcp-policy.yaml` covers the common cases deterministically;
    Haiku resolves ambiguous entries with disk-cached decisions.
    Per-project override at `<project>/.arkaos/mcp-override.yaml`
    (force_active wins on collision, with warning). Env vault at
    `~/.arkaos/secrets.json` (chmod 600 enforced) injects secrets into
    `.mcp.json`; missing vars listed in `.env.arkaos.example`.
  - **Agent Provisioning** (Sub-feature C): stack-based baseline sync
    (Phase 8) populates `<project>/.claude/agents/` from
    `config/agent-allowlists/<stack>.yaml`. PreToolUse hook
    (`agent-provision.sh`) intercepts `Task` calls for missing agents and
    copies them from core at runtime, with hardened path-traversal
    defenses (allowlist regex + `resolve().relative_to()` containment +
    atomic write). Auto-creation via Skill Architect deferred to v2.18.0.
  - **Self-healing Sync** (Sub-feature D): `run_with_retry` wrapper with
    exponential backoff; `SyncError` structured-error model with
    grep-able codes; integration test asserts full-sync idempotence
    across two consecutive runs.

### Changed

- Reporter now aggregates content sync, MCP optimizer warnings, and agent
  provisioning errors into `SyncReport.errors` — no more silent failures.
- `McpSyncResult` extended with `mcps_deferred` and `optimizer_warnings`.

### Security

- PreToolUse hook for agent provisioning validates `subagent_type` against
  a strict allowlist regex before any filesystem operation. Source agent
  lookup + target write-path are confined to `departments/` and
  `.claude/agents/` via `Path.resolve()` containment checks. Atomic writes
  prevent corrupt half-provisioned agent files.
- MCP env vault refuses to load world- or group-readable `secrets.json`;
  refusal surfaces as a structured warning in the sync report.

### Tests

- 2292 passing (2244 baseline + 48 new across A/B/C/D). Zero regressions.

## [2.16.1] - 2026-04-12

### Fixed

- Descriptor syncer crashed with `IndexError: list index out of range` when a
  project descriptor had a scalar `stack:` value instead of a YAML list
  (affected `lora-tester` and `purz-comfyui-workflows`). The syncer now
  coerces scalar strings to single-element lists, tolerates `None`, and drops
  empty tokens during normalization. Affected descriptor files were also
  normalized to the canonical list form.

## [2.1.0] - 2026-04-05

### Added
- **Dashboard** (Nuxt 4 + NuxtUI v4 + FastAPI) — 7-page monitoring UI
  - Overview with stats cards
  - Agent browser with pagination, filters, detail page with full DNA profile
  - Command search with department filter
  - Budget visualization per tier
  - Task monitor with status tabs
  - Knowledge base stats + semantic search
  - System health checks
  - `npx arkaos dashboard` to start both servers
- **Knowledge Ingest** via dashboard UI
  - YouTube URL → download → transcribe → index
  - PDF upload → extract → index
  - Audio (MP3/WAV) → transcribe → index
  - Web URL → scrape → index
  - Markdown/TXT → direct index
  - Real-time progress tracking with polling
- FastAPI backend (13 REST endpoints, port 3334)
- Auto-start script for dashboard servers

### Fixed
- Agent detail page routing (Nuxt nested route conflict)
- SSR disabled for dashboard (local tool, no SSR needed)

## [2.0.3] - 2026-04-05

### Added
- Local vector knowledge DB with Synapse L3.5 KnowledgeRetrieval layer (fastembed + sqlite-vss)
- `npx arkaos index` to index Obsidian vault into vector DB
- `npx arkaos search "query"` for semantic knowledge search
- `npx arkaos init` for per-project configuration (.arkaos.json)
- V1 detection alert in hooks with migration instructions
- 3 Tier 3 support agents: Maria (Research), Isabel (Docs), Tomas Jr (Data)
- Project squad template for cross-department teams

### Fixed
- PM escalation: Carolina → COO Sofia (was bypassing to CTO)
- Quality Gate trigger clarified: once per workflow, not per phase
- Nested subagent policy documented: max 1 level
- Cross-tier collaboration: Tier 2 agents can collaborate directly in project squads

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
