# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.81.0] - 2026-05-25

### Added (Settings expansion: Profile + Projects + Keys — PR63)

- **`core/profile/manager.py`** — safe read/write of
  `~/.arkaos/profile.json`. `ProfileManager.patch(updates)` merges
  with stored data, sanitises (only writable fields, string coercion,
  bumps `updated` timestamp, preserves `created`), atomic write via
  `.tmp + os.replace()`. Never raises on disk failures — caller
  always gets a `Profile` back.
- **`parse_projects_dirs(value)`** — extracts absolute path tokens
  from the free-text `projectsDir` (handles the historical schema
  `"/path/A para X, /path/B para Y"` used by the sync engine).
- **`GET /api/profile`** and **`POST /api/profile`** endpoints —
  returns the profile with a `projects_dirs_list` convenience field;
  POST patches with writable-field whitelist.
- **`dashboard/app/pages/settings.vue`** restructured with a
  left-side section nav + three sections:
  - **Profile** — name, company, role, language, market, vaultPath
  - **Projects** — projectsDir textarea + live parsed-paths preview
  - **API Keys** — existing functionality, polished into the new shell
- Future sections (MCPs, Hooks, Plugins, Theme) marked as PR63b in
  the nav footer so the operator sees they're coming.

### Test coverage

- 23 new `tests/python/test_profile_manager.py` cases:
  - 5 `Profile.from_dict` (defaults, known fields, unknown drop,
    coercion, non-dict guard)
  - 4 `ProfileManager.read` (missing file, valid file, corrupt JSON,
    top-level array)
  - 7 `ProfileManager.patch` (first write, merge, unwritable drop,
    timestamp bump, created preservation, coercion, disk failure)
  - 7 `parse_projects_dirs` (empty, single, comma-separated, prose,
    first-path-per-segment, home-relative, non-path skip)
- Vue typecheck clean
- Full Python suite: 3735/3735 passing

## [2.80.0] - 2026-05-25

### Added (Shared `DashboardState` component — PR64)

- **`dashboard/app/components/DashboardState.vue`** consolidates the
  loading / error / empty triple that was duplicated (with subtle
  drift — different icon sizes, inconsistent ARIA roles, some
  retry buttons missing) across five dashboard pages.
- **Slots**: `default` (success content), `loading`, `error`,
  `empty` — all overridable. Sensible defaults.
- **Props**: `status` (Nuxt `AsyncDataRequestStatus`), `error`,
  `empty`, `emptyTitle`, `emptyDescription`, `emptyIcon`,
  `loadingLabel`, `onRetry`.

### Refactored

- `dashboard/app/pages/index.vue` — overview now uses `DashboardState`
- `dashboard/app/pages/health.vue` — empty state is now consistent
  with the rest of the dashboard
- `dashboard/app/pages/tasks.vue`
- `dashboard/app/pages/budget.vue`
- `dashboard/app/pages/agents/index.vue`

Net code reduction: 5 × ~15 lines of duplicated boilerplate removed,
replaced by one ~100-line component that ships consistent ARIA roles
and retry-button affordances. The next dashboard PRs (PR63 Settings,
PR65 Budget rebuild, PR66 Index → command center) inherit this
foundation.

### Test coverage

- Vue typecheck clean for the new component + 5 refactored pages
- Full Python suite: 3712/3712 (no backend changes)
- Preflight: `all_passed: True`

## [2.79.0] - 2026-05-25

### Added (Persona builder wizard — PR62)

- **`dashboard/app/components/PersonaWizard.vue`** — 4-step wizard
  closing the loop on PR57's backend (`POST /api/personas/build`):
  1. **Sources** — operator types the person's name and pastes URLs
     (one per line, up to 50). Optional "skip ingest" checkbox if
     content is already indexed.
  2. **Indexing** — fires `POST /api/knowledge/ingest-bulk` (PR56),
     subscribes to `/ws/tasks` for per-job progress, auto-advances
     when every job is `completed` or `failed`.
  3. **Generating DNA** — calls `POST /api/personas/build`; reads the
     indexed chunks via the multi-backend `LLMProvider` and produces
     a draft `Persona`.
  4. **Review & save** — operator edits any field (Identity, DNA,
     Knowledge), optionally checks "Also clone to an agent
     immediately" with department + tier pickers. Save calls
     `POST /api/personas` and (when requested) `.../clone`.
- **`dashboard/app/pages/personas.vue`** — header now offers two
  creation paths: `AI Builder` (primary, opens the wizard) +
  `Manual` (legacy 30-field form, preserved for power users who
  want to type every DNA value). The wizard never auto-saves; every
  transition is operator-confirmed.

### Why

`[[project_persona_builder]]` memory explicitly flagged the manual
form as the wrong UX ("form is too tall, no overflow scroll") and
specified the wizard shape. PR57 shipped the backend (the builder
+ endpoint + 14 tests). PR62 ships the frontend that consumes it.
Together they implement the complete plan from the project memory.

### Test coverage

- Vue typecheck clean for the new component
- Full Python suite: 3712/3712 passing (no backend change in this PR)
- Preflight: `all_passed: True`

### Operator action

This PR ships the wizard code but does **not** include a Vitest
suite (dashboard/ has no test infra yet — separate PR worth). Verify
the four-step flow in browser after merge: run `cd dashboard && pnpm dev`
and `python3 scripts/dashboard-api.py`, then `/personas` → `AI Builder`.

## [2.78.0] - 2026-05-25

### Added (One-stop `/arka update` orchestrator — PR61)

- **`core/sync/update_orchestrator.py`** — version-drift-aware
  wrapper around the existing sync engine. On every `/arka update`:
  1. Reads the running ArkaOS version from `<repo>/VERSION`.
  2. Probes the npm registry for the published latest (5s timeout,
     1-hour disk cache at `~/.arkaos/npm-latest.cache.json`).
  3. If older, shells out to `npx arkaos@latest update` and waits
     for it to finish (10-min timeout). The npx step rewrites
     `~/.arkaos/.repo-path` to the freshly-extracted package so the
     sync engine below reads the right code.
  4. Dispatches the existing `run_sync()` engine — same arguments,
     same telemetry, same report shape.
- **Skill rewired** — `departments/ops/skills/update/SKILL.md` now
  points `/arka update` at the orchestrator instead of the bare
  engine. The engine remains the documented fallback for callers
  that don't need the version-drift gate.

### Bug fixed

Operators were running `/arka update` inside Claude Code without
first running `npx arkaos@latest update`. Result: the sync engine
silently ran from whichever npx cache `~/.arkaos/.repo-path` last
pointed at — months-stale in some cases (e.g. `v2.39.0` from
2026-05-14 in the dev environment that built this PR). Every
intervening release became invisible to `/arka update`.

Confirmed local repro: `cat ~/.arkaos/.repo-path` →
`/Users/.../node_modules/arkaos` at v2.39.0; `npm view arkaos
version` → v2.77.0 (the version published by PR60). 38 releases
silently skipped.

### Safety

- Never raises on transient failures: npm offline, slow registry,
  missing `npx` → orchestrator falls through to the engine using
  whatever code is currently installed (= identical to pre-PR61).
- Version-drift detection only triggers `npx` when *both* installed
  and latest are readable semver — defends against probe garbage.
- Probe TTL caps registry traffic to once per hour per machine.

### Test coverage

- 29 new `tests/python/test_update_orchestrator.py` cases:
  - Semver shape: 8 parametrised cases (canonical, prerelease,
    leading-`v`, missing patch, garbage, oversized)
  - Semver compare: 5 parametrised older-than cases
  - npm probe: fresh cache hit, expired cache refresh, timeout,
    non-zero exit, garbage output, OSError
  - End-to-end orchestrate: runs npx on stale, skips on current,
    skips on probe-None, skips on installed-None, always returns
    a SyncReport
  - `_run_npx_update` never raises: OSError, TimeoutExpired,
    non-zero returncode
- Full Python suite: 3712/3712 passing
- Preflight: `all_passed: True`

## [2.77.0] - 2026-05-25

### Added (Cost-category env var + Codex headless auto-detect — PR60)

- **`ARKA_CALL_CATEGORY` env var** read by `_record` and
  `_log_fallback` in `core/runtime/llm_provider.py`. Orchestration
  layers can set it before invoking the provider so `/arka costs`
  (PR47's `by_category` aggregation) attributes spend by skill /
  subagent / plugin / MCP server. Empty / unset → base bucket
  (backward-compat).
- **Codex CLI `headless_supported()` auto-detects PATH** — adapter
  reports `True` whenever the `codex` binary is on PATH. When the
  operator installs Codex CLI later, the adapter lights up without a
  code change (`headless_complete` still raises until the invocation
  syntax is verified, but the supported gate now responds correctly).
- **Codex error messages split by situation** — missing binary
  carries the install hint; binary-present-but-unverified carries the
  syntax-verification checklist. Cleaner operator UX in both cases.

### Why

- Cost category: PR47 added `by_category` aggregation but the field
  was never populated automatically — every row landed in the `""`
  bucket. PR60 closes that loop with the env-var pattern (orchestrator
  sets, provider reads).
- Codex auto-detect: TODO comment was dated 2026-04-20 and the
  `headless_supported()` returning hard `False` blocked any future
  fast-path discovery. Auto-detect is the lowest-friction unblock.

### Test coverage

- 3 new `test_pr60_*` cases in `test_llm_provider.py` (env var flows,
  unset → base bucket, whitespace stripping)
- 3 new `TestImprovedCodexTodoMessage` cases in
  `test_gemini_cli_headless.py` (missing-binary install hint,
  present-binary syntax hint, `headless_supported` reflects PATH)
- Full Python suite: 3683/3683 passing
- Preflight: `all_passed: True`

### Deferred

- Setting `ARKA_CALL_CATEGORY` at specific orchestration points (skill
  execution, subagent dispatch, plugin invocation, MCP server call)
  is an opt-in follow-up. Operator can grep callers and wire env-var
  sets where useful.

## [2.76.0] - 2026-05-25

### Added (Closing-marker soft block — PR59)

- **`core/governance/closing_marker_check.py`** — response-side
  classifier for `[arka:phase:13]` / `[arka:trivial]` closing markers.
  Mirrors `meta_tag_check` (PR30) and `kb_cite_check` (PR18). Trivial-
  length bypass (under 15 words) skips the check.
- **Stop hook wires it in** — `closing_marker_check_passed` +
  `closing_marker_check_reason` now appear on every
  `stop-hook-flow-check` row in `~/.arkaos/telemetry/enforcement.jsonl`;
  result JSON persists to `/tmp/arkaos-closing/<session>.json` so the
  next UserPromptSubmit can surface a nudge.
- **UserPromptSubmit surfaces the nudge** as a third `[arka:suggest]`
  line (alongside KB-cite + meta-tag), gated by the same effort
  threshold (low/medium suppress, high/xhigh/default surface).

### Why

Telemetry analysis from the May 24-25 session showed **0% closing-
marker rate** on flow-required turns (5/5 rows with neither
`[arka:phase:13]` nor `[arka:trivial]`). The model finishes the work
but skips the wrap-up tag that lets telemetry confirm the turn closed
cleanly. PR59 follows the proven PR29→PR30 pattern: surface the gap,
close it with soft-block enforcement.

### Test coverage

- 15 new `tests/python/test_closing_marker_check.py` cases (present /
  trivial-length / missing / defensive edges / result immutability)
- 2 new `tests/hooks.bats` cases (high effort surfaces, low effort
  suppresses) — `hooks.bats` 20/20 passing minus the pre-existing
  unrelated constitution-L0 failure
- Full Python suite: 3678/3678 passing

## [2.75.0] - 2026-05-25

### Changed (Workflow classifier widened — PR58)

- **`config/hooks/_lib/workflow-classifier.sh`** verb pattern extended
  with continuation, ship-tier, and improvement verbs. Telemetry from
  the May 24-25 session showed **97% classifier-did-not-match**
  across 495 enforcement rows — most missed prompts were short
  continuations (`continua`, `força`) or ship verbs (`ship`,
  `publish`, `merge`, `release`, `deploy`) that prolonged in-flight
  work that the classifier should have flagged.

### New verbs in the pattern

- Portuguese: `continuar`, `força`, `colocar`, `pôr`/`por`, `melhorar`,
  `terminar`, `acabar`, `publicar`, `lançar` + their conjugations
- English: `continue`, `continuing`, `ship`, `merge`, `publish`,
  `release`, `deploy`, `finish`, `improve` + their conjugations
- Also fixed: the existing `fazer` pattern missed bare `faz` (3-char
  form); the optional-char fix catches it now.

### Why

Without this, follow-up prompts in a long continuous-build session
went unmeasured — no `[ARKA:WORKFLOW-REQUIRED]` injection, no Stop-
hook telemetry. The compliance dashboard couldn't surface gaps it
should have surfaced. PR58 closes that measurement gap before any
further enforcement decisions.

### Test coverage

- 27 new `tests/workflow-classifier.bats` cases (4 legacy creation
  verbs, 16 new continuation/ship/improvement verbs, 7 negative
  cases: questions, slash commands, bang shells, empty, single-word
  greetings)
- `tests/hooks.bats` still 18/18 passing (no regression)
- Full Python suite: 3663/3663 passing
- Preflight: `all_passed: True`

## [2.74.0] - 2026-05-25

### Added (AI-powered persona builder — PR57)

- **`core/personas/builder.py`** generates persona drafts from
  already-indexed vector-store content. Searches the store for chunks
  about the target person, joins them up to a 18 000-char context
  window, sends the bundle to the configured LLM via the
  multi-backend `LLMProvider` (Claude Code subagent / Anthropic API /
  Ollama local — per `[[feedback_multi_backend_not_single]]`), parses
  the JSON response into a `Persona` model.
- **`POST /api/personas/build`** wires the dashboard up:
  ```
  {"name": "Alex Hormozi", "search_query": "...", "top_k": 20,
   "source_label": "..."}
  ```
  → `{persona: <draft>, chunks_used: N, provider_name: "..."}`.
  The draft is **never saved** — operator reviews and calls
  `POST /api/personas` to persist.
- **Robust JSON extraction** — the parser tolerates LLM responses
  that wrap the JSON in markdown fences or add leading prose. Bare
  arrays are rejected so a malformed shape can't sneak through.
- **System prompt enforces the full DNA schema** — DISC, Enneagram,
  Big Five, MBTI, mental models, expertise domains, frameworks, key
  quotes (verbatim only), communication style.

### Flow

Closes the project memory plan
`[[project_persona_builder]]`: user provides sources → existing
`IngestEngine` indexes them → `PersonaBuilder.generate(name)` analyses
the chunks → draft Persona surfaced for review → operator edits and
saves via existing CRUD endpoints. Multi-step wizard UX still owed on
the Vue side; backend + builder are ready.

### Test coverage

- 14 new `tests/python/test_persona_builder.py` cases:
  - JSON extraction across bare / fenced / leading-prose / non-JSON /
    bare-array shapes
  - End-to-end build with a fake provider + fake store
  - Name fallback to search query, explicit query override, context
    truncation, no-chunks raise, empty-name raise, non-JSON raise,
    schema-violation raise, system-prompt propagation
- Full Python suite: 3663/3663 passing

## [2.73.0] - 2026-05-25

### Added (Bulk URL ingestion — PR56)

- **`POST /api/knowledge/ingest-bulk`** — accepts
  `{"sources": ["url1", "url2", ...]}` and queues one background job
  per source via the existing `IngestEngine` pipeline. Validation:
  rejects non-list payloads, empty/whitespace-only entries, non-string
  entries; dedupes; caps at 50 sources per request.
- **`Bulk` input mode in the knowledge dashboard page** — paste a list
  of URLs (one per line) and ship them as a batch. Live count of
  detected sources, over-cap warning, button label reflects pending
  source count.

### Why

Heavy KB-builders ingest dozens of YouTube videos, articles, and PDFs
per session — the URL-at-a-time UX was a friction point. Bulk mode
turns a batch into one paste-and-go action while reusing the same
per-job WebSocket progress stream the single-source flow already
ships.

### Test coverage

- 9 new `tests/python/test_knowledge_bulk_ingest.py` cases:
  validation rejection paths (non-list / empty / whitespace / over-cap),
  dedup, whitespace stripping, result aggregation, per-source error
  doesn't abort batch, non-string entries skipped.
- Full Python suite: 3649/3649 passing.

## [2.72.0] - 2026-05-25

### Added (ArkaOS as Claude Code plugin marketplace — PR55)

- **`.claude-plugin/marketplace.json`** turns the `andreagroferreira/arka-os`
  repo into a Claude Code plugin marketplace consumable by anyone:
  ```
  /plugin marketplace add andreagroferreira/arka-os
  /plugin install arkaos-dev-skills@arkaos
  ```
- **Bundle `arkaos-dev-skills`** ships the 10 portable skills generated
  by PR51 (`code-review`, `tdd-cycle`, `runbook`, `spec`, `db-design`,
  `security-audit`, `clean-code-review`, `api-design`, `refactor-plan`,
  `architecture-design`).
- **`marketplace/skills/README.md`** regenerated with install
  instructions and the catalog, sorted alphabetically.

### Pivot from PR51 plan

The original PR51 plan was to PR our skills into `github.com/anthropics/skills`.
After inspecting that repo: it's a curated first-party showcase
(Anthropic-authored skills, 16,598 forks for consumption), not an
open submission marketplace. Anthropic's contribution model is
**"host your own marketplace"** — the `/plugin marketplace add <owner>/<repo>`
flow. PR55 implements that pattern, which puts WizardingCode in
control of the bundle name, versioning, and skill curation.

### Test coverage

- 1 new `test_marketplace_manifest_is_valid_json` (parses, declares
  `arkaos`, ships all 10 skills under `arkaos-dev-skills`)
- Full Python suite: 3640/3640 passing

## [2.71.0] - 2026-05-25

### Added (Opt-in `/goal` integration into scheduler — PR54)

- **`ScheduleConfig.goal_condition` + `task_budget`** — new optional
  YAML fields that map to Claude Code v2.1.139's `/goal` primitive.
  When set, the scheduler appends `--goal <condition> --task-budget <N>`
  to the `claude -p` argv so the model keeps running until it decides
  the condition is satisfied, instead of stopping when the prompt's
  hardcoded phases run out.
- **Pairing guard** — setting `goal_condition` without a positive
  `task_budget` raises `ValueError`. Per KB note
  `[[2026-05-12-claude-code-2-1-139-goal-agent-view]]`: sharp edges
  around the model overcommitting to ambiguous goals → infinite-loop
  risk. The budget caps the metered burn.
- **Production schedules untouched** — both fields default to `None`,
  so existing operator schedules ship byte-identical argv. Opt-in
  only.

### Migration note

The Anthropic Agent SDK $200 credit policy still applies on
2026-06-15 (see PR52). Adopting `/goal` increases the number of
turns per run, so flipping a schedule to goal-driven completion
*after* the cutover should pair with a direct-API-key invocation
(or stay on the python_module path for Dreaming v2). The
`metered-billing-warned.<command>` marker from PR52 continues
to fire on any legacy `claude -p` schedule regardless of /goal.

### Test coverage

- 4 new `tests/python/test_scheduler_daemon.py` cases:
  - YAML loader picks up `goal_condition` + `task_budget`
  - Both unset → legacy argv (byte-identical to pre-PR54)
  - Both set → argv gains `--goal <cond> --task-budget <N>`
  - `goal_condition` without `task_budget` → ValueError raised
- Full scheduler suite: 23/23 passing

## [2.70.0] - 2026-05-25

### Changed (Flow enforcer lookback widened 6 → 20 — PR53)

- **`core/workflow/flow_enforcer.ASSISTANT_WINDOW`** bumped from `6`
  to `20`. The 6-message window was too tight for long multi-PR
  sessions: after a single PR's worth of test runs / commits / npm
  publishes (each producing a substantive assistant message), the
  `[arka:routing]` marker aged out and the enforcer blocked subsequent
  Edit/Write calls even when the operator was clearly mid-scope.
  Surfaced repeatedly during the May 24-25 7-PR adoption arc — used
  `ARKA_BYPASS_FLOW=1` multiple times as a workaround. PR53 closes
  that carry-forward.
- **Transcript remains authoritative** per ADR
  `docs/adr/2026-04-17-binding-flow-enforcement.md` — the change just
  widens the lookback before declaring the marker absent.

### Test coverage

- 1 new regression test (`test_pr53_marker_at_position_15_still_found`)
  verifies a routing line emitted 15 messages back is found — would
  have been invisible under the old window.
- Existing `test_assistant_window_after_pr53_widening` updated to lock
  the new value at 20.
- Full Python suite: 3635/3635 passing.

## [2.69.0] - 2026-05-25

### Added (Portable Agent Skills export — PR51, Angle C)

- **`scripts/marketplace_export.py`** generates open-spec-compliant
  exports of the ten outward-facing development skills (per KB note
  `[[2026-04-25-agent-skills-open-standard]]` Angle-C recommendation):
  `code-review`, `tdd-cycle`, `runbook`, `spec`, `db-design`,
  `security-audit`, `clean-code-review`, `api-design`, `refactor-plan`,
  `architecture-design`.
- **Output: `marketplace/skills/<slug>/SKILL.md`** + catalog `README.md`.
  Conforms to the open spec at https://agentskills.io so the skills run
  inside any compliant runtime (Claude Code, Codex CLI, Cursor, VS Code
  Copilot, Atlassian, Figma).
- **Non-destructive** — in-tree skills under `departments/dev/skills/`
  keep their ArkaOS-specific KB-first prefix and `allowed-tools` field
  for the Claude Code path. The export script generates a portable
  copy each time it runs.

### Transformations applied

1. Strip the `<!-- arka:kb-first-prefix … -->` block (depends on
   Obsidian MCP — ArkaOS-specific).
2. Normalise frontmatter `name` — drop `dev/`, `arka-dev-`, `arka-`
   namespace prefixes so the spec sees the bare slug.
3. Drop `allowed-tools` (Claude Code-specific grammar).
4. Strip ArkaOS slash-command references (`/dev`, `/arka`, etc.)
   from header lines so the skill is verb-driven, not invocation-bound.

### Submission to anthropic/skills

Fork-and-PR remains a manual step (operator's call on timing and
which exports to upstream). Run `python3 scripts/marketplace_export.py`
to regenerate the bundle before submitting.

### Test coverage

- 13 new `tests/python/test_marketplace_export.py` cases (per
  transformation + end-to-end on the real source tree)
- Full Python suite: 3634/3634 passing

## [2.68.0] - 2026-05-25

### Added (Metered-billing cutover warning — PR52)

- **Scheduler emits a one-time stderr warning** when a schedule still
  uses the legacy `claude -p` invocation. Anthropic's Agent SDK $200
  credit policy takes effect **2026-06-15**: programmatic Claude usage
  (`claude -p`, Agent SDK, GitHub Actions, third-party harnesses) is
  metered separately from interactive subscription credit (Pro $20 /
  Max5x $100 / Max20x $200, no rollover). Operator action: migrate the
  affected schedule to `python_module` (Dreaming v2 path) or to a
  direct API key with explicit budget alarms.
- Warning is **one-time per schedule** via a marker under
  `~/.arkaos/telemetry/metered-billing-warned.<command>`. Stays out of
  the way of operators who have already migrated.
- The `python_module` path (Dreaming v2) is never warned — it's the
  migration target, not the deprecated route.

### Audit findings (PR52)

- Dreaming v2 already lives on `python_module`, so the production
  cognitive loop is **not** at risk on 2026-06-15.
- GitHub Actions workflows (publish/release/test) do **not** call
  `claude`, so CI is not affected.
- Only legacy `prompt_file`-only schedules in the operator's
  `~/.arkaos/schedules.yaml` trigger the warning. If none exist,
  the warning never fires.

## [2.67.0] - 2026-05-25

### Added (worktree.baseRef = head — Claude Code adoption arc PR48)

- **`installer/worktree-baseref.js`** seeds `worktree.baseRef = "head"`
  into `~/.claude/settings.json` on every Claude Code install/update.
  Claude Code v2.1.151+ ships the `worktree.baseRef` setting; the
  default branches new worktrees from the repo's main branch. For
  ArkaOS's iterative feature-branch workflow we want worktrees to
  branch from current HEAD instead, so an agent working off a feature
  branch gets a worktree built on top of it (not master).
- **Operator overrides preserved** — the seeder only writes when the
  key is missing. If a value already exists (including `"main"` set
  explicitly by the operator), it stays.
- **Merge-safe** — if `worktree` exists with other subkeys but no
  `baseRef`, the seeder merges `baseRef` in without touching siblings.
- Default also added to `config/settings-template.json` so first
  installs (no prior settings.json) get the value via the bootstrap
  jq merge in `install.sh`.

### Test coverage

- 7 new `tests/installer/worktree-baseref.test.js` cases (runtime
  gating, missing-settings, create, preserve unrelated keys,
  operator override, idempotency, merge with sibling subkeys).
- Full installer suite: 66/66 passing.

## [2.66.0] - 2026-05-25

### Added (Per-category usage breakdown — Claude Code adoption arc PR47)

- **`category` field on every telemetry row** — `record_cost` now
  accepts an optional `category` arg mirroring Claude Code v2.1.149's
  per-category usage breakdown. Free-form string: callers ship
  `"skill:<slug>"`, `"subagent:<dept>"`, `"plugin:<id>"`,
  `"mcp:<server>"`, or `""` for base usage. Backward-compatible —
  existing JSONL rows without a `category` field land in the `""`
  bucket.
- **`CostSummary.by_category`** populated by the aggregator using the
  same `_group` helper as `by_provider` / `by_model`.
- **`/arka costs` renders a "By category" section** when at least one
  categorised row exists. Pure markdown table, sorted by cost desc.
  Hidden when telemetry is legacy-only so old vaults don't grow an
  empty section.

### Test coverage

- 4 new `tests/python/test_llm_cost_telemetry.py` cases (writer
  records category; default empty; aggregator groups; legacy
  unmigrated rows fall into the `""` bucket).
- 2 new `tests/python/test_llm_cost_telemetry_cli.py` cases (CLI
  renders "By category" when present; hides it for legacy-only data).
- Full cost-telemetry suite: 50/50 passing.

## [2.65.0] - 2026-05-25

### Added (Effort-aware nudge gating — Claude Code adoption arc PR46)

- **Effort-aware `[arka:suggest]` surfacing** (PR46) — both the Stop and
  UserPromptSubmit hooks now read Claude Code's W19 `effort.level`
  signal from hook stdin (`.effort.level` JSON field) with
  `$CLAUDE_EFFORT` env-var fallback. The soft-block nudges (KB-cite
  + meta-tag) only surface to the next turn when effort is
  `high` / `xhigh` (or unset, defaulting to high). On `low` / `medium`
  the nudges are suppressed so cheap exploratory turns don't drag the
  full ArkaOS contract along for every paragraph.
- **Telemetry labelling for nudge suppression** — every
  `stop-hook-flow-check` record in `~/.arkaos/telemetry/enforcement.jsonl`
  now carries an `effort_level` field, so `/arka costs` and future
  compliance reports can compute suppression rates per effort tier.
- **Test coverage** — five new `tests/hooks.bats` cases lock the gating
  (low/medium suppress, high surfaces, default surfaces, `$CLAUDE_EFFORT`
  fallback honoured).

### Design note

Telemetry is cheap and feeds compliance dashboards, so the kb_cite,
meta_tag, and sycophancy detectors continue to run on every Stop turn
regardless of effort. Effort only gates the *next-turn nudge surfacing*
because that costs model tokens. Hard enforcement (PreToolUse
`flow_enforcer`) is unaffected and runs at every effort level.

## [2.64.0] - 2026-05-25

### Added (Hard deny defaults — Claude Code adoption arc PR45)

- **`autoMode.hard_deny` seeder** (PR45) — Claude Code v2.1.131+ shipped
  unconditional deny rules. New `installer/hard-deny.js` ships a curated
  default list (destructive git, filesystem destruction, secrets paths,
  privilege escalation, `curl | sh`) and merges it into
  `~/.claude/settings.json` on every `npx arkaos install` / `update`.
  Operator-authored rules in `settings.json` and entries in
  `~/.arkaos/hard-deny.json` are preserved on every run.
- **Behaviour** — idempotent (string-equality merge, no duplicates),
  atomic write (.tmp + rename), no-op when runtime is not Claude Code,
  no-op when settings file missing. Eight new tests in
  `tests/installer/hard-deny.test.js` lock the contract.
- **Why** — without `hard_deny`, auto mode is structurally unsafe: an
  allow rule can shadow a deny one. The seeder closes that gap by
  default on every install, no operator action required.

## [2.63.0] - 2026-05-24

### Added (Mandatory post-task skill evaluation — PR44)

- **`mandatory-skill-evaluation` NON-NEGOTIABLE rule** added to
  `config/constitution.yaml`. Stop hook now invokes
  `core/governance/skill_proposer.evaluate` on every closing assistant
  message. Bypass gates: explicit skip markers, no-completion-signal,
  trivial-length (<15 words), below-skill-hint floor (needs ≥2 of:
  10-phase / workflow / skill / template / procedure / playbook /
  checklist). Surviving turns generate a Markdown proposal under
  `~/.arkaos/skill-proposals/<date>-<slug>.md` for later promotion.
- **Test fixtures** — `tests/python/test_constitution.py` updated for
  24 NON-NEGOTIABLE / 39 total rule IDs.

## [2.62.0] - 2026-05-24

### Added (Automatic Claude Code plugin installation — PR43)

- **`frontend-design@claude-plugins-official`** auto-installed on every
  `npx arkaos install` / `update` when the runtime is Claude Code. The
  installer detects the runtime, shells out to `claude plugins install`,
  and tracks the result in `~/.arkaos/plugins-installed.json`. Failures
  are non-fatal — the rest of the install proceeds. Test suite in
  `tests/installer/plugin-install.test.js` mocks the shell-out and
  locks the idempotent behaviour.

## [2.61.0] - 2026-05-24

### Added (Community department — twelfth pattern repeat, ARC COMPLETE)

- **`/community model` workflow** (PR42) — new
  `departments/community/workflows/model.yaml`. 11-phase Enterprise
  workflow building a community business model. Phases: brief →
  purpose-definition (parallel: Beatriz + Mateus) → ideal-member-
  profile → SPACES-classification → two-sided-value-prop (parallel:
  Beatriz + Eduardo) → platform-fit → monetisation (parallel:
  Beatriz + Helena) → growth-loop (parallel: Beatriz + Luna) →
  self-critique → Quality Gate (opus) → delivery.

### Arc complete

Twelve user-facing-feature PRs closed (PR31 → PR42) covering every
department where an Enterprise-tier command lacked a workflow. The
audit-first / workflow + skill-expansion template is now codified
and repeatable. Every Enterprise-tier command across the system
either has a production workflow or never claimed Enterprise tier
(Sales, Fin, Leadership).

## [2.60.0] - 2026-05-24

### Added (SaaS department — eleventh pattern repeat, three workflows)

- **`/saas plg` workflow** (PR41) — 10-phase Enterprise workflow.
  Freemium vs trial vs reverse-trial model selection + activation
  event design + onboarding optimisation + monetisation trigger
  + expansion mechanics (NRR > 110%) + instrumentation. Multi-
  functional: Tiago + Helena (CFO unit-economics) + Carolina
  (Product) + Sofia D (UX) + Francisca (Tech).
- **`/saas growth` workflow** (PR41) — 10-phase Enterprise
  workflow. Stage diagnosis (seed / Series A / scale) + stage-
  appropriate metrics + motion × channel fit + team allocation
  + budget × runway + 90-day experiment portfolio. Multi-
  functional: Tiago + Helena + Tomas + Luna + Sofia (COO).
- **`/saas launch` workflow** (PR41) — 10-phase Enterprise
  workflow. Launch readiness audit + positioning + asset
  inventory + channel sequence + hour-by-hour launch day
  runbook + week-1/month-1 post-launch plan.

### Pattern arc (11 PRs deep)

Brand → GTM → Site → Marketing → Strategy → Content → PM → KB
→ Org → Ecom → SaaS. Only community remains in the user-facing
dept arc (2 Enterprise gaps).

## [2.59.0] - 2026-05-24

### Added (E-commerce department — tenth pattern repeat, three workflows in one PR)

- **`/ecom audit` workflow** (PR40) — 10-phase Enterprise workflow.
  Baymard + Nielsen UX audit + technical SEO + Core Web Vitals
  performance + brand-voice content audit + ResearchXL conversion
  audit → ICE-prioritised remediation plan.
- **`/ecom marketplace` workflow** (PR40) — 10-phase Enterprise
  workflow. Governance model + catalog architecture + vendor
  onboarding + order/fulfilment + payments/payouts + analytics
  stack. Multi-vendor + Mirakl/Amazon/Shopify aware.
- **`/ecom launch` workflow** (PR40) — 10-phase Enterprise workflow.
  Positioning + pricing ladder + content assets + channel mix +
  ad creative + day-by-day launch sequence with inventory-aware
  demand curve.
- **`skills/product-launch/SKILL.md` expanded** (32 → 191 lines).
  Positioning frame (e-commerce specific with onlyness + price
  tier), 4-tier pricing ladder with margin floor per tier,
  complete content asset inventory, channel ramp priority matrix,
  T-30 to T+14 day-by-day launch sequence template,
  inventory-aware demand curve with sold-out scenario playbook,
  explicit kill-switch criteria, 5 common failure modes.

## [2.58.0] - 2026-05-24

### Added (Org department — ninth pattern repeat)

- **`/org culture` workflow** (PR39) — new
  `departments/org/workflows/culture.yaml`. 10-phase Enterprise
  workflow defining org culture operationally. Phases: brief →
  archaeology (parallel: Sofia + Clara) → values-set (parallel:
  Sofia + Tomas) → behaviours → rituals → decision-principles
  (parallel: Sofia + Marta) → operationalisation → self-critique
  → Quality Gate (opus) → delivery.
- **`skills/culture-define/SKILL.md` expanded** (32 → 169 lines).
  Inversion Test (the only test that matters — values must have
  defensible opposites held by reputable companies), cultural
  archaeology (extract as-is before defining aspirational),
  behaviour mapping with observable + coachable criteria, ritual
  catalogue with load-bearing classification, decision principles
  YAML format (fast lane / slow lane / disagree-and-commit /
  escalation), operationalisation into hiring + onboarding +
  performance + promotion, 5 common failure modes including
  Platitude Values and Wall Poster Syndrome.

## [2.57.0] - 2026-05-24

### Added (KB department — eighth pattern repeat)

- **`/kb persona` workflow** (PR38) — new
  `departments/kb/workflows/persona.yaml`. 10-phase Enterprise
  workflow building or refining a callable persona from KB
  sources. Phases: brief → source-gathering → belief-extraction
  (parallel: Clara + Pedro) → voice-pattern (parallel: Clara +
  Eduardo) → expertise-domains → decision-patterns →
  advisor-profile → self-critique → Quality Gate (opus) →
  delivery.
- **`skills/persona-build/SKILL.md` expanded** (32 → 211 lines).
  Source inventory format with diversity floor, belief inventory
  with citation requirements (2+ citations per belief, 4+ for
  load-bearing), 4-layer voice pattern extraction (lexical +
  syntactic + rhetorical + tonal), expertise map with deep /
  surface / no-go classification, decision pattern catalogue with
  cited examples, 4-framework Behavioral DNA scoring (DISC +
  Enneagram + Big Five + MBTI) with source-evidence requirement,
  callable advisor YAML schema, 5 common failure modes.

## [2.56.0] - 2026-05-24

### Added (PM department — seventh pattern repeat, three workflows in one PR)

- **`/pm discover` workflow** (PR37) — 10-phase Enterprise
  workflow. Teresa Torres Opportunity Solution Tree + assumption
  mapping + 2-week experiments. Phases: brief →
  opportunity-mapping → interview-plan → interview-execution →
  opportunity-selection → assumption-tests → experiment-execution
  → self-critique → Quality Gate (opus) → delivery.
- **`/pm roadmap` workflow** (PR37) — 9-phase Enterprise workflow.
  Outcome-driven roadmap with three horizons + bet selection +
  capacity allocation + per-audience communication.
- **`/pm shape` workflow** (PR37) — 10-phase Enterprise workflow.
  Shape Up pitch (Basecamp) — appetite + boundaries + rough
  solution + rabbit holes + no-gos + betting decision.
- **`skills/roadmap-build/SKILL.md` expanded** (32 → 137 lines).
  North Star math constraints (lagging+leading+causal+movable),
  outcome tree decomposition math, three-horizon commitment
  policy, Bets vs Promises distinction (with failure criteria
  required on bets), capacity allocation policies (fixed time
  vs fixed scope vs invalid both), per-audience communication
  matrix, 5 common failure modes.

### Pattern arc (7 PRs deep)

Brand → GTM → Site → Marketing → Strategy → Content → PM. 3
workflows in one PR (vs the usual 2) because PM had a 3-gap
clean sweep and the template was fluent. Remaining: kb (2),
org (2), ecom (3), saas (4), community (2).

## [2.55.0] - 2026-05-24

### Added (Content department — sixth pattern repeat)

- **`/content system` workflow** (PR36) — new
  `departments/content/workflows/system.yaml`. 10-phase Enterprise
  workflow: brief → pillar-design → format-stack → production-
  cadence → distribution-channels → analytics-stack → ops-systems
  → self-critique → Quality Gate (opus) → delivery. Builds a full
  Content Operating System with pillars + cadence + cross-channel
  derivatives + analytics dashboard spec.
- **`/content youtube` workflow** (PR36) — new
  `departments/content/workflows/youtube.yaml`. 10-phase Enterprise
  workflow: brief → channel-positioning → title × thumbnail
  architecture (parallel: Rafael + Isabel) → hook + script
  structure (parallel: Rafael + Teresa) → SEO + metadata → cadence
  → distribution → self-critique → Quality Gate (opus) → delivery.
- **`skills/youtube-strategy/SKILL.md` expanded** (32 → 161
  lines). Added: CTR-retention math (median + top-performer
  benchmarks), 7 named title × thumbnail patterns with use cases,
  thumbnail visual hierarchy rules, hook architecture (4-stage
  first-30s template), 10-12min script structure with retention
  drop points, SEO metadata stack YAML format, publishing cadence
  math with 90-day targets, cross-platform derivative spec (3-5
  shorts + thread + LinkedIn + newsletter + podcast).

## [2.54.0] - 2026-05-24

### Added (Strategy department — fifth pattern repeat)

- **`/strat blue-ocean` workflow** (PR35) — new
  `departments/strategy/workflows/blue-ocean.yaml`. 10-phase
  Enterprise orchestration. Phases: brief → red-ocean canvas →
  ERRC grid (parallel: Tomas + Rita) → non-customer analysis →
  blue-ocean canvas → viability test (parallel: Tomas + Helena) →
  execution plan → self-critique → Quality Gate (opus) → delivery.
- **`/strat growth` workflow** (PR35) — new
  `departments/strategy/workflows/growth.yaml`. 10-phase Enterprise
  orchestration. Phases: brief → Greiner diagnosis → Ansoff Matrix
  (parallel: Tomas + Rita) → adjacency analysis (parallel: Tomas +
  Helena) → vector selection → risk-feasibility (parallel: Tomas +
  Helena) → 12-month roadmap → self-critique → Quality Gate (opus)
  → delivery.
- **`skills/growth-strategy/SKILL.md` expanded** (32 → 161 lines).
  Added: Greiner 6-phase model with predictable crises, Ansoff
  Matrix 2×2 with risk-adjusted sequencing, Chris Zook adjacency
  framework with empirical success-rate math, growth vector
  decision tree, risk profile YAML template with pre-mortem
  format, 12-month roadmap template with decision gates per
  quarter, 5 common failure modes.

### Audit revealed (uncovered surface)

Cross-departmental Enterprise gap audit ran for the first time
this PR: 12+ Enterprise-tier commands remain across 9 departments
that lack workflow YAMLs. Sales is unique — zero Enterprise
commands declared. Remaining gap-rich depts: content, pm, kb,
org, ecom, saas, community.

## [2.53.0] - 2026-05-24

### Added (Marketing department — fourth pattern repeat)

- **`/mkt growth-loop` workflow** (PR34) — new
  `departments/marketing/workflows/growth-loop.yaml`. 10-phase
  Enterprise orchestration: brief → retention-baseline → loop-type
  selection → loop-design → compounding-math → instrumentation
  (parallel: marketing + tech) → 30-day experiment plan →
  self-critique → Quality Gate (opus) → delivery. Cross-validates
  unit economics with CFO (Helena) parallel review in the
  compounding-math phase.
- **`skills/growth-loop/SKILL.md` expanded** (64 → 181 lines).
  Added: loop type decision matrix (viral / paid / content /
  product / community) with retention minimums + unit economics
  thresholds, 5 loop types fully spec'd with worked examples and
  failure modes, loop specification YAML format (4-step structure),
  8-point pre-instrumentation design checklist, 5 common failure
  modes across all loop types.

### Pattern (fourth repeat — Marketing follows Brand → GTM → Site)

PR31 Brand → PR32 GTM → PR33 Site (Landing) → PR34 Marketing.
Each PR fills the single biggest Enterprise-tier gap in its
department per the same audit shape. Pattern is now textbook —
Sales, Strategy, Content, Community follow next.

## [2.52.0] - 2026-05-24

### Added (Landing/Site department — user-facing feature)

- **`/landing funnel` workflow** (PR33) — new
  `departments/landing/workflows/funnel.yaml`. 10-phase Enterprise
  orchestration: brief → awareness diagnosis → funnel-type
  selection (Value Ladder) → offer design (Grand Slam) → page
  architecture → email sequences → metrics targets → self-critique
  → Quality Gate (opus) → delivery. Selects squeeze / tripwire /
  SLO / webinar / VSL / application funnel matched to awareness ×
  price.
- **`/landing webinar` workflow** (PR33) — new
  `departments/landing/workflows/webinar.yaml`. 10-phase Enterprise
  orchestration: brief → hook & promise → registration page →
  reminder sequence → live script → replay & cart sequence →
  conversion targets → self-critique → Quality Gate (opus) →
  delivery.
- **`skills/webinar-funnel/SKILL.md` expanded** (32 → 185 lines).
  Added: Perfect Webinar timing frame (Brunson), false belief
  pattern template (6-step teardown), registration page anatomy
  with conversion targets, 5-email reminder sequence template,
  full pitch script structure with 7 timed sections, 5-7 email
  replay/cart sequence, pixel-event tracking spec with attribution
  windows.

### Pattern (third repeat)

PR31 (Brand) → PR32 (GTM cross-departmental) → PR33 (Landing/Site).
Same shape every time: SKILL.md promises Enterprise outcome,
underlying artifact is a stub, audit identifies, PR ships full
workflow + framework-dense skill spec. Pattern is now repeatable
across remaining departments (Marketing, Sales, Strategy, Content,
Community).

## [2.51.0] - 2026-05-24

### Added (GTM department — cross-departmental feature)

- **`/saas gtm` workflow** (PR32) — new
  `departments/saas/workflows/gtm-strategy.yaml`. 9-phase Enterprise
  cross-departmental orchestration: brief → ICP discovery (parallel
  Strategy + SaaS) → positioning (Brand + Strategy) → motion
  selection (SaaS + Sales) → channel mix (Marketing + Landing) →
  90-day plan (SaaS + Marketing + Sales) → self-critique →
  Quality Gate (opus) → delivery. First cross-departmental
  Enterprise workflow in the system — orchestrates five separate
  departments through a single command.
- **`skills/gtm-strategy/SKILL.md` expanded** (32 → 158 lines).
  Added: ICP template (firmographics + persona + pain + signal),
  Onlyness positioning frame with 3-test validation, 6 GTM
  motions comparison table with CAC payback windows, channel-
  motion matrix, 90-day execution plan template with named
  owners, 1-page executive summary contract.

### Pattern

Same shape as PR31 (Brand): SKILL.md promised Enterprise outcome,
delivered a stub. Audit identifies it, PR closes the gap with
production workflow + framework-dense skill spec. Pattern is now
repeatable across departments — Marketing / Sales / Strategy /
Landing each have analogous gaps.

## [2.50.0] - 2026-05-24

### Added (Brand department — user-facing feature)

- **`/brand audit` workflow** (PR31) — new
  `departments/brand/workflows/audit.yaml`. 8-phase Enterprise-tier
  orchestration: brief → asset-gather → 7-element-mapping (parallel)
  → 21-point scoring → competitor benchmark → self-critique →
  Quality Gate (opus) → delivery. Closes a tier-contract violation
  where SKILL.md flagged `/brand audit` as Enterprise but no
  workflow YAML existed.
- **`/brand design-system` workflow** (PR31) — new
  `departments/brand/workflows/design-system.yaml`. 8-phase
  Enterprise-tier orchestration: brief → token-design → atom-
  molecule-organism (parallel) → template-page → WCAG AA audit →
  self-critique → Quality Gate (opus) → delivery. Same tier-
  contract closure.
- **`skills/primal-audit/SKILL.md` expanded** (57 → 130 lines) —
  added per-element scoring rubric (3 sub-criteria each = 21
  total), evidence citation contract, competitor benchmark table
  template, ranked remediation plan with leverage ratings.
- **`skills/design-system/SKILL.md` expanded** (33 → 204 lines) —
  added two-layer token JSON schema, Atomic Design 5-level
  component manifest with props + a11y notes, WCAG 2.2 AA gates
  per criterion, Storybook CSF3 export contract, integration
  guide.

### Why this lands now

User-facing Brand department feature. Closes the audit gap
identified by the brand-strategist self-audit: SKILL.md promised
two Enterprise-tier commands that delivered single-skill stubs
instead of multi-phase Quality-Gated workflows.

## [2.49.0] - 2026-05-24

### Added

- **Meta-tag soft block** (PR30) — `core/governance/meta_tag_check.py`
  is a response-side classifier mirroring `kb_cite_check` (PR18). Stop
  hook writes per-session result to `/tmp/arkaos-meta/<session>.json`
  (owner-only via umask 0o077). UserPromptSubmit hook surfaces a
  `[arka:suggest]` nudge on the next turn when the previous
  substantive response was missing the `[arka:meta] kb=N research=X
  persona=Y gap=Z critic=W` one-liner.
- **11 unit tests** covering present/bypass/missing/result-shape paths.
- **Stop-hook telemetry** gains `meta_tag_check_passed` and
  `meta_tag_check_reason` fields alongside the existing kb_cite,
  sycophancy, and closing-marker signals.

### Why this lands now

PR29's `/arka compliance` summary surfaced a 0.00% meta-tag rate
on 272 real stop-events. The contract from PR12 (v2.34.0) was being
recorded in telemetry but never enforced or nudged. PR30 closes that
gap with the same soft-block pattern that worked for KB-first.

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
