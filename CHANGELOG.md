# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.48.0] - 2026-05-24

### Added

- **Behavior compliance summarizer** (PR29) — new
  `core/governance/compliance_telemetry.py` reads stop-hook entries
  from `~/.arkaos/telemetry/enforcement.jsonl` and reports compliance
  with the four contracts the session-start hook establishes:
  - `closing_marker_found` (`[arka:phase:13]` / `[arka:trivial]`)
  - `meta_tag_found` (`[arka:meta]` one-liner, PR12 v2.34.0)
  - `kb_cite_passed` (KB citation soft block, PR18 v2.40.0)
  - sycophancy clean (inverse of flagged, PR13 v2.35.0)
- **`/arka compliance [period]` command** — markdown table with
  per-contract rates. Periods today/week/month/all share the
  vocabulary of `/arka enforcement` and `/arka costs`.
- **10 unit tests** covering missing/empty file, null fields excluded
  from denominators, period filter, perfect/mixed/zero compliance,
  invalid period raises.

### Surfaced

- **Detection-logic gap (telemetry quality)** — first real run against
  the operator's KB shows 272 stop-events but compliance rates near
  zero for meta_tag / kb_cite / sycophancy fields (consistent null
  values in JSONL). PR30 will diagnose the stop-hook detection
  pipeline and bring the data quality up before promoting any of
  these contracts from warn-only to blocking.

## [2.47.0] - 2026-05-24

### Added

- **Installer user-data scaffolding** (PR28) — `npx arkaos install` and
  `npx arkaos@latest update` now create the operator-mutable files
  the discipline-arc commands depend on:
  - `~/.arkaos/redaction-clients.json` with an empty `clients` list +
    `_doc` field explaining how to populate it. Fresh installs no
    longer have a silent leak scanner.
  - `~/.arkaos/reorganize-proposals/` directory so the session-start
    stale-aware trigger and `/arka reorganize` have a write target
    on day zero.
- **`installer/user-data-scaffold.js`** — idempotent: never overwrites
  operator-authored content. Returns a per-resource status object.
- **5 installer tests** covering create / preserve / idempotent paths.

## [2.46.3] - 2026-05-24

### Documentation

- README.md updated to list the new `/arka` commands shipped in the
  discipline arc: `/arka enforcement`, `/arka reorganize`, and the
  release preflight CLI (`python -m core.release.preflight_cli`).
  Test-suite footnote bumped from 3,025 → 3,473+ tests.

## [2.46.2] - 2026-05-24

### Documentation

- Backfilled CHANGELOG entries for v2.40.0–v2.46.1 (9 releases shipped
  in the 24h discipline arc). Range v2.18.0–v2.39.0 acknowledged as a
  detailed-history gap with summary themes; `git log --oneline
  v2.17.5..v2.40.0` remains authoritative for per-commit detail.

## [2.46.1] - 2026-05-24

### Fixed

- **Preflight `_run() None` branch coverage** — 5 new tests cover
  `FileNotFoundError` / `TimeoutExpired` paths for npm-auth,
  npm-publish-capability, gh-auth, git-remote, git-clean. Each check
  degrades gracefully when the underlying CLI isn't installed or hangs.
- **PAT-in-URL credential leak in `check_git_remote`** —
  `_redact_git_credentials` strips `user:token@` segments from remote
  URLs before they reach the CLI output. SSH URLs pass through unchanged.
- **`/tmp/arkaos-cite` permissions on multi-user systems** — Stop hook
  wraps the cite-file write in `os.umask(0o077)` so the directory is
  `0o700` and JSON file is `0o600` — owner-only. No-op on single-user
  dev boxes.

## [2.46.0] - 2026-05-24

### Added

- **Stale-aware reorganizer trigger** (PR24) — session-start hook
  auto-fires `python -m core.cognition.reorganizer_cli` in background
  with a 30s timeout when today's proposal file is missing. No cron,
  no platform-specific scheduler — file existence is the signal.
- **`core/cognition/reorganizer_scheduler.py`** — `is_stale()`,
  `status_summary()`, `render_status_md()` for the new `/arka status`
  Reorganization section.
- **`/arka status` Reorganization section** — surfaces today's proposal
  path + artifact count alongside LLM costs and Enforcement.

## [2.45.0] - 2026-05-24

### Fixed

- **39 historical client-name leaks scrubbed** (PR23) — 33 in test
  fixtures (test_dreaming, test_obsidian_cataloger, test_research_profiler,
  test_retrieval, test_sync_discovery, test_learning_detector) replaced
  with synthetic equivalents (acmecorp / clientalpha / globexsa). 6 doc
  files sanitized (CHANGELOG L28, 1 ADR, 4 superpowers specs).
- **`check_no_client_name_leaks` severity flipped to BLOCKING** —
  PR22 shipped at WARNING to avoid blocking the very release that
  introduced the scanner. With historical leaks scrubbed, the check is
  now blocking by default. Regression test locks the contract.

## [2.44.0] - 2026-05-24

### Added

- **Client-name leak scanner** (PR22) — `core/governance/leak_scanner.py`
  scans tracked source files for word-boundary matches against the
  operator's user-local `~/.arkaos/redaction-clients.json`. Empty/missing
  config is a no-op (no false positives in CI clones).
- **`check_no_client_name_leaks` preflight check** — runs on every
  release preflight, surfaces leaks with `file:line` and matched token.
  Ships at WARNING severity initially (see v2.45.0 for the BLOCKING flip).

## [2.43.0] - 2026-05-24

### Added

- **Release preflight gate** (PR21) — step 0 of the release pipeline.
  Six checks before the irreversible tag/push/publish steps: version
  alignment, npm-auth, npm-publish-capability, gh-auth, git-remote,
  git-clean. Exit 1 on any blocking failure. Closes a debt from
  v2.40.0 release (1h lost because expired npm token only surfaced
  post-merge).
- **`/arka enforcement` command** — exposed in `arka/SKILL.md`.

## [2.42.0] - 2026-05-24

### Added

- **Dreaming → Agent reorganizer** (PR20) — `core/cognition/reorganizer.py`
  scans the KB for pattern/anti-pattern/lesson markdown files, sanitizes
  client identifiers, renders a markdown proposal at
  `~/.arkaos/reorganize-proposals/<date>.md`. **Propose-only** — never
  modifies agent YAMLs. Cron + auto-PR creation deferred.
- **`/arka reorganize [--since-days N] [--dry-run]`** — manual command.

### Fixed

- **Markdown pipe injection in proposal table cells** — `_md_escape`
  applied to every rendered cell.
- **`output_dir` path traversal** — `_validate_output_dir` allowlist
  (`~/.arkaos` or system tempdir).
- **Same-day rerun torn-write** — atomic `tmp + os.replace()`.

## [2.41.0] - 2026-05-24

### Added

- **Hard enforcement default** (PR19) — `hooks.hardEnforcement = true`
  is now the default for fresh installs and unset configs. Explicit
  user `false` preserved.
- **`core/governance/enforcement_telemetry.py`** — line-streamed
  JSONL summarizer over `~/.arkaos/telemetry/enforcement.jsonl`.
- **`/arka enforcement [period]` command** — markdown aggregation:
  total calls, block rate, top blocked tools, top reasons. Periods:
  today/week/month/all.
- **`installer/config-seed.js`** — idempotent `~/.arkaos/config.json`
  seed during install/upgrade. Atomic write. Preserves user choice.
- **`/arka status` Enforcement section** — surfaces today's
  compliance numbers alongside LLM costs.

### Changed

- **Tighter `Decision.to_stderr_message`** — 4-line verbose form
  compressed to one line; same contract tokens preserved; adds
  `ARKA_BYPASS_FLOW=1` hint.

## [2.40.0] - 2026-05-23

### Added

- **KB-first soft block** (PR18) — `core/governance/kb_cite_check.py`
  is a citation classifier. Stop hook writes a per-session result to
  `/tmp/arkaos-cite/<session>.json`; UserPromptSubmit hook surfaces a
  `[arka:suggest]` nudge in the next turn's `additionalContext` when
  the previous response was on an ArkaOS topic without `[[wikilink]]`,
  `[knowledge:` marker, or `file:line` reference.
- **`safe_session_id` wrapper** — prevents path traversal via
  malicious session_id (`../../../tmp/pwn` → no write).

### Fixed

- **ReDoS in `_FILE_LINE_PATTERN`** — bounded quantifiers + 50KB scan
  cap. Pathological 100KB input now completes <500ms (was ~41s).

## [v2.18.0 – v2.39.0] - 2026-04-17 → 2026-05-13

This range corresponds to the **Conclave Phase 5** governance batch
plus the v2.18.0–v2.31.x development sprints. Detailed entries were
not written at the time. See `git log --oneline v2.17.5..v2.40.0`
for the per-commit history. Notable themes:

- Conclave Phase 5 governance layer (PR10 v2.32.0 — constitution)
- Discovery vs Effect taxonomy (PR11 v2.33.0 — Bash classifier)
- `[arka:meta]` transparency tag (PR12 v2.34.0)
- Sycophancy detector (PR13 v2.35.0 — `arkaos-not-yes-man`)
- Definition-of-Done gates (PR14 v2.36.0)
- Checkpoint primitives MVP (PR15 v2.37.0)
- Hybrid learning detector (PR16 v2.38.0)
- Pack-safety / repo sanitization (PR17 v2.39.0)
- Dreaming v2 (insights, KB cataloger, auto-documentor)
- Job queue, dashboard, websocket-ingest
- User-data separation (`~/.arkaos/` canonicalisation)

## [2.17.5] - 2026-04-17

### Fixed

- **KB Cache TTL eviction bug** — `_evict_expired()` now called on every `store()` call
  to proactively evict expired entries. Previously expired entries only evicted on reads,
  causing them to accumulate on disk. Default TTL raised 30min → 90min,
  max_entries raised 50 → 150.
- **conclave/SKILL.md** — Added compact 20-advisor table inline to fix
  `test_skill_md_lists_all_20_advisors` assertion.

## [2.17.4] - 2026-04-16

### Changed

- **Sprint 10: Lazy-Load Skills** — All skill SKILL.md files trimmed to ≤120 lines.
  Thin orchestrators kept in SKILL.md; deep content moved to `references/` subdirectory.
  20 SKILL.md files updated across departments and arka/ meta-skills.
  Forbidden patterns and advisor tables extracted to reference files.
  12 project-specific skills removed from shared repo (client_media, client_fashion,
  client_energy, client_commerce, lora-tester, client_advisory, client_retail, client_publisher, wizardingcode,
  client_video, scaffold, saas-scaffold) per client instruction.

## [2.17.3] - 2026-04-16

### Changed

- Updated HookShell dispatch to route `PreToolUse` events through the
  new `dispatch_to_shell()` function in `hooks/user-prompt-submit.sh`.

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
