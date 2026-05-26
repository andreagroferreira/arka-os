# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.53.1] - 2026-05-26

### Fixed (PR95c round-trip test was destructive — hotfix)

The merge test ran a real `dev → ops` move and shifted every real
dev agent into ops. Reverted immediately. Test rewritten with
`monkeypatch` to stub `agent_move`.

### Lesson

Cross-cutting "do-it-all" endpoint tests (merge, migrate, bulk-delete)
must stub the destructive primitives. Never assume "the test only
touches fixtures".

## [3.53.0] - 2026-05-26

### Added (Department merge — PR95c)

`/departments/{id}` gets a Merge dropdown that moves every agent in
the current department into another. Reuses agent_move per file.
Tier 0 skipped, empty src aborts. Atomic + reversible per-agent via
/trash.

### Backend

- `POST /api/departments/{src}/merge-into/{dst}` (NEW) — fs walks src
  dir + agent_move per id. Returns moved/skipped/failed counts. 6
  new tests.

### Frontend

- `/departments/[dept].vue` — warning-tinted Merge dropdown in
  navbar. Confirm dialog. Navigates to /departments on success.

### Files changed

- `scripts/dashboard-api.py` — POST merge endpoint
- `tests/python/test_department_merge.py` (NEW, 6 tests)
- `dashboard/app/pages/departments/[dept].vue` — Merge UI

## [3.52.0] - 2026-05-26

### Added (Inline agent YAML editor — PR95b)

Mirrors PR94d (workflow YAML editor) for agents. **Edit YAML** button
in the agent detail hero opens a modal with the raw YAML in a
monospace textarea + Save / Cancel.

### Backend

- `PUT /api/agents/{agent_id}/yaml` (NEW) — accepts
  `{content: "<YAML>"}`. Validates: dict root + non-empty `id` field
  + id matches URL param. Refuses Tier 0 (C-Suite) edits — those
  remain YAML-direct only. Atomic write (tmp + replace).
- 7 unit tests cover non-object body, empty content, unknown agent,
  non-dict root, id mismatch, Tier 0 refusal, round-trip preservation.

### Frontend

- `agents/[id].vue` — **Edit YAML** button next to the existing
  YAML download. Opens a UModal with a 20-row UTextarea. Save calls
  the PUT endpoint, surfaces parse/validation errors as toasts,
  refreshes the agent on success.

### Files changed

- `scripts/dashboard-api.py` — PUT /api/agents/{id}/yaml
- `tests/python/test_agent_yaml_update.py` (NEW, 7 tests)
- `dashboard/app/pages/agents/[id].vue` — Edit YAML button + modal

## [3.51.0] - 2026-05-26

### Added (Terminal page with allowlist commands — PR95a)

Operator-requested terminal in the dashboard. Ships as a controlled
command runner with a server-enforced allowlist. xterm.js / vue-termui
PTY can come as a follow-up if needed.

### Backend

- `TERMINAL_ALLOWLIST` (NEW) — 6 commands shipped (arkaos status,
  git status, git log, npm view arkaos version, pytest --collect-only,
  ls -la).
- `GET /api/terminal/commands` — returns id + label + description.
  Does NOT leak the underlying argv array.
- `POST /api/terminal/exec` — accepts `{command_id}`, runs via
  `subprocess.run(shell=False)` with 15s timeout + 20K chars per
  stream cap. Rejects anything not on the allowlist.
- 9 unit tests cover allowlist exposure, body validation, rejection
  paths, smoke run, and no-shell invariants.

### Frontend

- `/terminal` page (NEW) — UButton grid of allowlisted commands +
  Recent runs history (last 20) with copy-to-clipboard + stderr
  highlighting.
- Sidebar Terminal nav item between Tasks and Workflows.

### Design rationale

- vue-termui is for building Vue TUIs that RUN in a terminal — not
  for embedding a shell in a browser. The dashboard instead ships a
  controlled runner: no shell, no PTY, no arbitrary execution.
- subprocess.run + shell=False + explicit argv kills shell injection.
  List endpoint omits argv so XSS can't enumerate or rewrite.

### Files changed

- `scripts/dashboard-api.py` — allowlist + 2 endpoints
- `tests/python/test_terminal_exec.py` (NEW, 9 tests)
- `dashboard/app/pages/terminal.vue` (NEW)
- `dashboard/app/layouts/default.vue` — Terminal nav item

## [3.50.0] - 2026-05-26

### Added (Inline workflow YAML editor — PR94d)

The `/workflows` side panel YAML tab gains **Edit** / **Save** /
**Cancel** buttons. Operator can patch a workflow's YAML in place
without leaving the dashboard.

### Backend

- `PUT /api/workflows/{workflow_id}/yaml` (NEW) — accepts
  `{content: "<full YAML>"}`, parses it, validates root-must-be-dict
  + non-empty `id` key, then writes atomically (`tmp + replace`).
  Refuses unknown workflow / empty content / invalid YAML / missing
  id. `_resolve_workflow_yaml` helper finds the path by id.
- 7 unit tests covering invalid body, empty content, unknown id,
  missing-id YAML, round-trip preservation, resolve helper.

### Frontend

- `workflows.vue` — YAML tab header gains an **Edit** button. While
  editing, the panel swaps the `<pre>` for a UTextarea with Save /
  Cancel. Save mutates local state immediately, then refreshes from
  the backend.
- Picking a different workflow row resets `editingYaml = false`.

### Safety

- Endpoint refuses to write if YAML doesn't parse or lacks `id`.
- Atomic write so a partial save can't corrupt the file.
- No path-traversal risk — the path comes from `_resolve_workflow_yaml`,
  not from the request body.

### Files changed

- `scripts/dashboard-api.py` — PUT /api/workflows/{id}/yaml + helper
- `tests/python/test_workflow_yaml_update.py` (NEW, 7 tests)
- `dashboard/app/pages/workflows.vue` — Edit / Save / Cancel UI

## [3.49.0] - 2026-05-26

### Added (Free-text diff visualisation — PR94c)

Compare views now show side-by-side line diff for bio Markdown and
communication tone. Red removed, green added.

### Frontend

- `TextDiff.vue` (NEW) — LCS-based line diff, no deps.
- `agents/compare.vue` — bio + tone diff blocks.
- `personas/compare-with-agent.vue` — same diff blocks.

### Files changed

- `dashboard/app/components/TextDiff.vue` (NEW)
- `dashboard/app/pages/agents/compare.vue` — diff sections
- `dashboard/app/pages/personas/compare-with-agent.vue` — same

## [3.48.0] - 2026-05-26

### Added (Persona archetypes catalog page — PR94b)

New `/personas/archetypes` route with a browseable card grid of the
8 starter archetypes from PR93b. Each card shows MBTI / DISC /
Enneagram badges + description + "Create from this" button that
deep-links to `/personas/new?archetype=<id>`. The wizard auto-detects
the query, switches to description mode, and pre-fills.

### Frontend

- `dashboard/app/pages/personas/archetypes.vue` (NEW) — card grid
  using the existing `/api/personas/archetypes` endpoint.
- `PersonaWizard.vue` — `watch(archetypes, ...)` reads
  `route.query.archetype` and applies the matching archetype on
  first load.
- `personas/index.vue` — "Archetypes" button in the navbar `#right`
  slot between Import and Export ZIP.

### Files changed

- `dashboard/app/pages/personas/archetypes.vue` (NEW)
- `dashboard/app/components/PersonaWizard.vue` — query auto-apply
- `dashboard/app/pages/personas/index.vue` — Archetypes nav button

## [3.47.0] - 2026-05-26

### Added (Read state on notifications — PR94a)

Bell badge counts only unread events. Each row shows a primary dot
when unread, dims to muted text once read. Click row to mark read;
**Mark all read** button in the popover header.

### Files changed

- `useActivityFeed.ts` — read state, markRead/markAllRead actions
- `NotificationsBell.vue` — unread dot, click-to-read, header action

## [3.46.0] - 2026-05-26

### Added (Notifications bell — PR93d)

Sidebar header gains a bell icon next to the color-mode button.
Click it to see the last 50 activity events: kind icon, title,
optional description + link, relative timestamp. Each entry can be
dismissed individually, and Clear empties the feed.

Persistence is client-only — `localStorage` key
`arkaos_activity_feed` (capped at 50 entries). No server roundtrip.

### New

- `useActivityFeed()` composable (createSharedComposable) — `push`,
  `clear`, `remove`, `load`, reactive `events` + `unreadCount`.
- `NotificationsBell.vue` — UPopover bell with unread badge, icons
  per kind, dismiss button per row, Clear button in header.
- Sidebar header layout extended to mount the bell next to the
  color-mode button (only when sidebar not collapsed).

### First integration

- Agents bulk-delete now pushes an event into the feed in addition
  to the toast. Routes the link to `/trash` so the operator can undo
  from one click. More integrations to come as the feed gets used.

### Files changed

- `dashboard/app/composables/useActivityFeed.ts` (NEW)
- `dashboard/app/components/NotificationsBell.vue` (NEW)
- `dashboard/app/layouts/default.vue` — mount the bell
- `dashboard/app/pages/agents/index.vue` — push event on bulk delete

## [3.45.0] - 2026-05-26

### Added (Bulk export selected personas — PR93c)

The personas bulk action bar gains an **Export ZIP** button. Select
N personas, click Export, download just those N.

### Backend

- `GET /api/personas/export-all.zip?ids=a,b,c` (extended) — optional
  id allow-list. 2 new tests.

### Frontend

- `personas/index.vue` — Export ZIP button in the bulk action bar.

### Files changed

- `scripts/dashboard-api.py` — `ids` query param
- `tests/python/test_personas_export_zip.py` — 2 new tests
- `dashboard/app/pages/personas/index.vue` — bulk Export

## [3.44.0] - 2026-05-26

### Added (Persona archetype templates — PR93b)

PersonaWizard ships 8 curated starter archetypes (Coach, Skeptic,
Founder, Operator, Strategist, Storyteller, Architect, Negotiator).
Pick one in the description mode and the wizard pre-fills name +
source + description.

### Backend

- `core/personas/archetypes.py` (NEW) — 8 generic archetypes
- `GET /api/personas/archetypes` (NEW). 7 unit tests.

### Frontend

- `PersonaWizard.vue` description mode gains a "Start from archetype"
  dropdown.

### Files changed

- `core/personas/archetypes.py` (NEW)
- `scripts/dashboard-api.py` — GET endpoint
- `tests/python/test_persona_archetypes.py` (NEW, 7 tests)
- `dashboard/app/components/PersonaWizard.vue` — dropdown

## [3.43.0] - 2026-05-26

### Added (Workflow phase agent links — PR93a)

Each phase card in the `/workflows` Flow tab now lists the agents
defined in that phase as small clickable badges. Click → land on
`/agents/{id}`. Replaces the previous "N agents" count badge.

### Backend

- `_summarise_phases` extended with `agent_ids: string[]` per phase
  derived from the YAML `agents[].agent_id` field. 1 new unit test
  (10 total).
- `agent_count` is now `len(agent_ids)`.

### Frontend

- `workflows.vue` — phase card replaces the count badge with a
  flex row of `<NuxtLink>` chips, one per agent. Each chip routes
  to the agent detail.

### Files changed

- `scripts/dashboard-api.py` — phases summary extended
- `tests/python/test_workflows_endpoint.py` — agent_ids test
- `dashboard/app/pages/workflows.vue` — phase chips

## [3.42.0] - 2026-05-26

### Added (Theme primary color picker — PR92d)

`/settings → Theme` gains a primary color picker. Operator picks one
of 8 Tailwind palette options (emerald default, plus blue / indigo /
violet / rose / amber / teal / cyan); the choice tints every primary
button, badge, link, and active state across the dashboard.

### Frontend

- `useThemeColor()` composable (NEW, `createSharedComposable`) —
  reads / writes `arkaos_theme_color` in `localStorage`, mutates
  `useAppConfig().ui.colors.primary` so the change is reactive.
- `default.vue` layout calls `loadFromStorage()` on mount so the
  preference applies before the first render flush.
- `settings.vue` — Theme section gains an 8-button color grid below
  the appearance picker. Selected button gets a primary border + tint.

### Files changed

- `dashboard/app/composables/useThemeColor.ts` (NEW)
- `dashboard/app/layouts/default.vue` — apply color on mount
- `dashboard/app/pages/settings.vue` — picker UI

## [3.41.0] - 2026-05-26

### Added (First-visit onboarding tour — PR92c)

A 6-step modal tour shows up on the first visit to `/` walking through
Agents → Personas → Workflows → Budget → keyboard shortcuts.

### Frontend

- `OnboardingTour.vue` (NEW) — UModal with progress bar, Back/Next,
  "Don't show again", per-step CTA. Dismissal persists in
  `localStorage` as `arkaos_onboarding_dismissed`.
- `default.vue` layout mounts the tour.

### Files changed

- `dashboard/app/components/OnboardingTour.vue` (NEW)
- `dashboard/app/layouts/default.vue` — mount the tour

## [3.40.0] - 2026-05-26

### Changed (Agent filters persisted in URL — PR92b)

`/agents` filter state (search + department + tier + DISC + MBTI
group + favorites-only) now lives in the URL query string. Deep
links survive reload, browser back/forward navigates between filter
states, and operators can share a filtered view by copying the URL.

### Query shape

- `q=<text>` — search
- `dept=<slug>` — department filter
- `tier=<0|1|2|3>` — tier filter
- `disc=<D|I|S|C>` — DISC primary
- `mbti=<analysts|diplomats|sentinels|explorers>` — MBTI group
- `fav=1` — favorites-only

Only non-default values are written, so the URL stays tidy.

### Files changed

- `dashboard/app/pages/agents/index.vue` — refs seeded from
  `route.query`, watcher pushes via `router.replace({ query })`

## [3.39.0] - 2026-05-26

### Added (Persona bulk ZIP export — PR92a)

Operator can now click **Export ZIP** on `/personas` to download every
persona in one archive. Each entry uses the same renderer as the
Obsidian vault sync, so the zip is a perfect mirror.

### Backend

- `GET /api/personas/export-all.zip` (NEW) — iterates
  `PersonaManager.list_all()`, renders each via
  `ObsidianPersonaStore._render`, packs into an in-memory
  `zipfile.ZipFile` with `ZIP_DEFLATED`. Filename uses persona name
  (sanitised + capped at 80 chars), with id-suffix fallback for
  collisions. Returns `application/zip`.
- `_zip_persona_slug` helper sanitises arbitrary names for archive
  members. 5 unit tests cover slug rules, length cap, missing
  manager, empty store, full archive contents.

### Frontend

- `personas/index.vue` — **Export ZIP** button next to Import in the
  navbar `#right` slot. Browser-native blob download.

### Files changed

- `scripts/dashboard-api.py` — GET /api/personas/export-all.zip + helper
- `tests/python/test_personas_export_zip.py` (NEW, 5 tests)
- `dashboard/app/pages/personas/index.vue` — Export ZIP button + handler

## [3.38.0] - 2026-05-26

### Added (Costs CSV export — PR91d)

Operator can now click **Export CSV** in the /budget navbar to
download every telemetry row for the active period.

### Backend

- `GET /api/llm-costs/export.csv?period=...` (NEW) — streams a
  `text/csv` with header + one row per telemetry entry. Columns:
  `ts`, `session_id`, `provider`, `model`, `category`, `tokens_in`,
  `tokens_out`, `cached_tokens`, `estimated_cost_usd`. Filename
  embeds the period: `arkaos-costs-month.csv`. Invalid periods fall
  back to `month`. 4 unit tests cover response shape, fallback
  behaviour, header presence, filename format.

### Frontend

- `pages/budget.vue` — Export CSV button next to Refresh in the
  navbar. Uses Blob URL + programmatic anchor click. Toast confirms.

### Files changed

- `scripts/dashboard-api.py` — GET /api/llm-costs/export.csv
- `tests/python/test_llm_costs_export.py` (NEW, 4 tests)
- `dashboard/app/pages/budget.vue` — Export button + handler +
  `apiBase` / `toast` destructure

## [3.37.0] - 2026-05-26

### Added (Workflow phase flow tab — PR91c)

`/workflows` side panel gains a **Flow** tab (default-selected) with a
vertical stepper of phases. Each phase shows name, gate-type badge,
agent count, and description. Operator can finally eyeball a workflow's
shape without reading YAML.

### Backend

- `/api/workflows` payload now includes a `phases: [{id, name,
  description, gate_type, agent_count}]` array per workflow. Distilled
  via `_summarise_phases` helper (NEW). Gate types tinted in the UI
  (user_approval → warning, quality_gate → error, automatic → primary).
- 3 new tests cover the summary shape, non-dict skipping, missing
  keys.

### Frontend

- `workflows.vue` — new Flow tab (selected by default when picking a
  row). Vertical stepper UI with left rail + numbered cards. Phase
  cards include gate + agent-count badges.
- Switching tabs no longer triggers another fetch — runs are still
  pre-loaded on row select.

### Files changed

- `scripts/dashboard-api.py` — phases summary + helper
- `tests/python/test_workflows_endpoint.py` — 3 new tests
- `dashboard/app/pages/workflows.vue` — Flow tab + stepper

## [3.36.0] - 2026-05-26

### Added (Persona import from URLs — PR91b)

`POST /api/personas/import` now accepts a `urls: [...]` array along
with `files: [...]`. URLs are fetched server-side (10s timeout,
http(s) only) and processed identically to local files.

### Backend

- `_fetch_url_entries(urls)` helper (NEW) uses `urllib.request` with a
  custom User-Agent. Bad schemes / fetch failures surface as
  per-row `fetch_error`. 4 new unit tests covering invalid scheme,
  empty list, non-list body, blank-string filtering.
- The endpoint preserves backward compatibility — operators that
  only send `files` still work.

### Frontend

- `personas/index.vue` — the Import button is now a dropdown with
  **Pick .md files…** and **From URLs…**. The URL flow opens a
  UModal with a textarea (one URL per line). Same toast summary on
  completion.

### Files changed

- `scripts/dashboard-api.py` — URLs accepted on import + helper
- `tests/python/test_personas_import.py` — 4 new tests (12 total)
- `dashboard/app/pages/personas/index.vue` — Import dropdown + URL modal

## [3.35.0] - 2026-05-26

### Added (Agent gap suggestions card — PR91a)

Home page gains a "What's missing?" card listing departments that
either have no agents at all or are missing a Tier 2 specialist.
Click any row to jump to `/agents/new`.

### Backend

- `GET /api/agents/suggestions?limit=N` (NEW) — walks the agent
  registry, compares against the 16 known department slugs, and
  returns gap rows tagged `high` (empty dept) or `medium` (no T2).
  7 unit tests cover payload shape, severity rules, limit
  truncation, known-departments constant.

### Frontend

- `AgentSuggestionsCard.vue` (NEW) — UCard mounted above the
  existing top-departments / recent-personas grid on the home page.
  Hides itself when there are no gaps.
- `pages/index.vue` — mounts the card above the existing row.

### Files changed

- `scripts/dashboard-api.py` — GET /api/agents/suggestions + constant
- `tests/python/test_agents_suggestions.py` (NEW, 7 tests)
- `dashboard/app/components/AgentSuggestionsCard.vue` (NEW)
- `dashboard/app/pages/index.vue` — mount the card

## [3.34.0] - 2026-05-26

### Added (Audit log page — PR90d)

The home page Recent Incidents card only shows the last 8 events.
PR90d adds a dedicated `/audit` route with filterable history (kind +
tool) reading the same enforcement telemetry log.

### Backend

- `GET /api/audit?limit=N&kind=...&tool=...` (NEW) — returns
  `{events: [{ts, tool, reason, cwd, bypass_used, kind}], total}`.
  `kind` filters by `bypass` / `blocked`, `tool` by exact name.
  Limit capped at 500. 7 unit tests cover empty log, zero limit,
  unknown kind, event shape, kind filter, cap enforcement.

### Frontend

- `dashboard/app/pages/audit.vue` (NEW) — filter bar (kind select +
  tool input), card list with kind-coloured badges, formatted
  timestamps, cwd path. Empty state confirms quiet workspace.
- Sidebar gains an "Audit" entry between Settings and Trash.

### Files changed

- `scripts/dashboard-api.py` — GET /api/audit
- `tests/python/test_audit_log.py` (NEW, 7 tests)
- `dashboard/app/pages/audit.vue` (NEW)
- `dashboard/app/layouts/default.vue` — Audit nav item

## [3.33.0] - 2026-05-26

### Changed (Budget trend window selector — PR90c)

The /budget trend chart was hard-coded to 7 days. PR90c adds a
**7 / 14 / 30** day selector right above the bars. Switches refetch
`/api/llm-costs/trend?days=N` in place — no other backend change.

### Frontend

- `dashboard/app/pages/budget.vue` — `trendDays` ref (7 default) +
  `USelect` near the chart header. `fetchApi` query is now reactive
  so a switch triggers a refresh.

### Files changed

- `dashboard/app/pages/budget.vue` — selector + reactive query

## [3.32.0] - 2026-05-26

### Added (Department comparison — PR90b)

`/departments/compare?a=dept1&b=dept2` shows two departments
side-by-side: agent count, workflow count, 30d calls + cost, agent
list, workflows list. Yellow tint on differing cells.

### Frontend

- `dashboard/app/pages/departments/compare.vue` (NEW) — uses the
  existing `/api/departments/{id}` endpoint twice, no new backend.
- `dashboard/app/pages/departments/[dept].vue` — Compare dropdown
  in the navbar `#right` slot listing every other department.

### Files changed

- `dashboard/app/pages/departments/compare.vue` (NEW)
- `dashboard/app/pages/departments/[dept].vue` — Compare dropdown

## [3.31.0] - 2026-05-26

### Added (Persona Markdown download — PR90a)

Sibling to PR89d for personas. Click **MD** on the persona hero to
save the full rendered Markdown (frontmatter + body sections) for
backup, cross-vault transfer, or sharing.

### Backend

- `GET /api/personas/{id}/markdown` (NEW) — rebuilds the Persona
  object from `persona_detail()` and renders via the same
  `ObsidianPersonaStore._render` used for vault sync. Output is
  byte-identical to what the operator would see in their vault.
  Responds with `text/markdown` and a sanitised filename. 4 unit
  tests cover error path, response shape, filename, body keys.

### Frontend

- `personas/[id].vue` — new **MD** button on the hero (between
  Clone and Edit). Browser-native download via Blob URL.

### Files changed

- `scripts/dashboard-api.py` — GET /api/personas/{id}/markdown
- `tests/python/test_persona_markdown_download.py` (NEW, 4 tests)
- `dashboard/app/pages/personas/[id].vue` — MD button + handler

## [3.30.0] - 2026-05-26

### Added (Agent YAML download — PR89d)

Click **YAML** on the agent hero to save the underlying YAML file
locally. Useful for cross-vault transfer, manual review, or backup
before doing aggressive edits.

### Backend

- `GET /api/agents/{id}/yaml` (NEW) — returns the raw YAML file as
  `application/x-yaml` with `Content-Disposition: attachment;
  filename="<id>.yaml"`. Refuses unknown agents. 4 unit tests cover
  error path, response shape, content-disposition format, body
  contains expected YAML keys.

### Frontend

- `agents/[id].vue` — third action button on the hero (between
  Export and Edit). Browser-native download via `Blob` URL +
  programmatic `<a download>` click. Toast confirms.

### Files changed

- `scripts/dashboard-api.py` — GET /api/agents/{id}/yaml
- `tests/python/test_agent_yaml_download.py` (NEW, 4 tests)
- `dashboard/app/pages/agents/[id].vue` — YAML button + handler

## [3.29.0] - 2026-05-26

### Added (Vault connection test in Settings — PR89c)

`/settings` profile section gains a **Test connection** button next
to the Vault path field. Click and the page tells you whether the
path exists and how many `.md` files live under `Personas/` and
`Agents/`. Tints green when reachable, yellow when not.

### Backend

- `GET /api/settings/vault` (NEW) — reads `profile.vaultPath`,
  reports `{configured, vault_path, exists, personas:{dir,count},
  agents:{dir,count}}`. Counts only `*.md` files. 6 unit tests cover
  unconfigured / missing-dir / configured-with-subdirs / payload
  shape / subdir invariants.

### Frontend

- `dashboard/app/pages/settings.vue` — Test connection button on the
  Vault path field. Auto-saves the path before testing so the
  backend sees the current value. Result card with tier-coloured
  border + subdir file counts.

### Files changed

- `scripts/dashboard-api.py` — GET /api/settings/vault
- `tests/python/test_settings_vault.py` (NEW, 6 tests)
- `dashboard/app/pages/settings.vue` — Test button + result card

## [3.28.0] - 2026-05-26

### Added (Workflow run history — PR89b)

The `/workflows` side panel gains a **Runs** tab next to YAML.
Workflows that tag their LLM calls with
`ARKA_CALL_CATEGORY=workflow:<id>` (new convention) get a session
roll-up showing recent runs with calls / cost / duration.

### Backend

- `GET /api/workflows/{id}/runs` (NEW) — parses PR47 telemetry JSONL
  filtered by `category == "workflow:<id>"`, groups by `session_id`,
  returns `{runs: [{session_id, started_at, ended_at, duration_s,
  calls, cost_usd, tokens_in, tokens_out}]}` sorted desc by start.
- Empty list when no matching telemetry exists (the common case
  until orchestrators opt in).
- `_iso_duration_s` helper handles both `+00:00` and `Z` suffixes.
- `_current_category` docstring updated to document the new form.
- 7 unit tests cover empty result, payload shape, limit=0, duration
  math (3 scenarios), malformed inputs.

### Frontend

- `dashboard/app/pages/workflows.vue` — side panel header now has
  YAML / Runs tabs. Picking a row pre-fetches its runs. Empty state
  surfaces the exact env var the operator needs to set.

### Files changed

- `core/runtime/llm_provider.py` — docstring extension
- `scripts/dashboard-api.py` — GET /api/workflows/{id}/runs + helper
- `tests/python/test_workflow_runs.py` (NEW, 7 tests)
- `dashboard/app/pages/workflows.vue` — Runs tab + loader

## [3.27.0] - 2026-05-26

### Added (Department pages — PR89a)

ArkaOS finally has a first-class view of its 16 departments. `/departments`
lists every dept with agent counts, tier distribution, 30d calls + cost.
Click → `/departments/{id}` for the full detail (agents grid, workflows
list, stats row).

### Backend

- `GET /api/departments` (NEW) — aggregates agent registry by
  department, merges with PR47 telemetry for 30d cost. Returns
  `{departments: [{department, agent_count, tier_counts, calls_30d,
  cost_usd_30d}], total}`.
- `GET /api/departments/{dept_id}` (NEW) — full detail including
  agent list (light shape) + workflows under
  `departments/<dept>/workflows/*.yaml` + 30d cost. Returns
  `{error: ...}` for unknown departments. 7 unit tests cover
  payload shape, sort order, required fields, error path, agent
  list, workflows, cost.

### Frontend

- `dashboard/app/pages/departments/index.vue` (NEW) — UTable with
  search filter, tier mini-badges, cost formatting.
- `dashboard/app/pages/departments/[dept].vue` (NEW) — stats row +
  agent grid (linking to `/agents/{id}`) + workflows list.
- Sidebar gains a "Departments" entry between Agents and Personas.

### Files changed

- `scripts/dashboard-api.py` — 2 new endpoints
- `tests/python/test_departments_endpoints.py` (NEW, 7 tests)
- `dashboard/app/pages/departments/index.vue` (NEW)
- `dashboard/app/pages/departments/[dept].vue` (NEW)
- `dashboard/app/layouts/default.vue` — Departments nav item

## [3.26.0] - 2026-05-26

### Added (Agent history timeline — PR88d)

Agent detail pages gain a History section showing the YAML file's
git log + any trash entries (delete / move). Combined into a single
chronological feed.

### Backend

- `GET /api/agents/{id}/history?limit=N` (NEW) — merges:
  - `git log --follow` on the agent YAML (hash, ISO date, author,
    subject) — best-effort, returns empty list on git failure or
    non-repo runs
  - Trash entries (`agent-delete`, `agent-move`) filtered by item_id
- Helpers `_agent_git_log`, `_trash_ts_to_iso`, `_trash_summary`
  extracted for testability. 7 unit tests cover unknown agent,
  payload shape, limit truncation, sort order, ts helper round-trip.

### Frontend

- `agents/[id].vue` — new `<section>` after the activity strip with
  a vertical timeline (UI: left border, dots, badge per kind,
  relative time, code hash, author). Hides itself when there's no
  history (e.g. uncommitted agent created via the dashboard).

### Files changed

- `scripts/dashboard-api.py` — GET /api/agents/{id}/history + helpers
- `tests/python/test_agent_history.py` (NEW, 7 tests)
- `dashboard/app/pages/agents/[id].vue` — timeline section + helpers

## [3.25.0] - 2026-05-26

### Added (Knowledge sources list + per-source delete — PR88c)

`/knowledge` was ingest-only. PR88c adds visibility: every distinct
source that contributed chunks now shows up as a list with chunk
counts and a per-row delete action.

### Backend

- `VectorStore.list_sources()` (NEW) — returns
  `[{source, chunks}]` sorted desc by chunk count, skipping the
  empty-source bucket. 5 unit tests covering empty store, distinct
  counting, sort order, blank-source exclusion + endpoint shape.
- `GET /api/knowledge/sources` (NEW) — wraps the method. Returns
  `{sources, total, error?}`.

### Frontend

- `dashboard/app/components/KnowledgeSourcesList.vue` (NEW) — card
  with search filter, paginated list (15 per page), per-row chunk
  badge + delete button (uses `useConfirmDialog`, `variant: danger`).
  Refresh button in the header. Pretty URL labels (host + path
  without `https://`).
- `dashboard/app/pages/knowledge.vue` — mounts the component below
  the existing ingest + search panels.

### Files changed

- `core/knowledge/vector_store.py` — `list_sources()`
- `scripts/dashboard-api.py` — GET /api/knowledge/sources
- `tests/python/test_knowledge_sources_list.py` (NEW, 5 tests)
- `dashboard/app/components/KnowledgeSourcesList.vue` (NEW)
- `dashboard/app/pages/knowledge.vue` — mount the list card

## [3.24.0] - 2026-05-26

### Added (Workflows page with YAML preview — PR88b)

A new `/workflows` route lists every workflow under
`departments/*/workflows/*.yaml` in a UTable + side-panel YAML
preview. Filter by department and search by name / command /
description / id.

### Backend

- `GET /api/workflows` (NEW) — scans every YAML, returns
  `{id, name, description, department, tier, command, phases_count,
  file, content}` per entry. Content ships in the payload so the
  side-panel renders without a second round-trip. 5 unit tests.

### Frontend

- `dashboard/app/pages/workflows.vue` (NEW) — UTable + side panel
  split. Filter bar (search + department). Tier badges tinted
  (enterprise → primary, focused → success, specialist → warning).
- Sidebar nav gains a "Workflows" entry between Tasks and Knowledge.

### Files changed

- `scripts/dashboard-api.py` — GET /api/workflows
- `tests/python/test_workflows_endpoint.py` (NEW, 5 tests)
- `dashboard/app/pages/workflows.vue` (NEW)
- `dashboard/app/layouts/default.vue` — Workflows nav item

## [3.23.0] - 2026-05-26

### Added (Persona vs Agent comparison — PR88a)

Persona detail hero gains a Compare dropdown listing every agent
linked to that persona. Pick one → land on a diff view at
`/personas/compare-with-agent?persona=p&agent=a`.

### Files changed

- `dashboard/app/pages/personas/compare-with-agent.vue` (NEW)
- `dashboard/app/pages/personas/[id].vue` — Compare dropdown

## [3.22.0] - 2026-05-26

### Added (Sidebar stats widget — PR87d)

A compact panel pinned above the bottom nav of the sidebar showing
agent / persona / department counts plus today's LLM spend + call
count. Polls every 60 seconds via a new lightweight endpoint.

### Backend

- `GET /api/sidebar-stats` (NEW) — returns
  `{agents, personas, departments, today_cost_usd, today_calls}`.
  Skips project scanning + incidents + quick actions so it's cheap
  enough to poll. 3 unit tests covering payload shape, non-negative
  invariants, and cost-is-float-or-none.

### Frontend

- `dashboard/app/components/SidebarStatsWidget.vue` (NEW) — fetches
  on mount, refreshes every 60s via `setInterval`. Hides itself on a
  collapsed sidebar so it doesn't fight for space when the user
  shrinks the nav. Cost helper handles `<$0.01` and `$0.xxx` /
  `$x.xx` formatting.
- `default.vue` layout mounts the widget between the top nav menu
  and the bottom nav (`mt-auto` so the bottom nav still sticks to
  the floor when the page is short).

### Files changed

- `scripts/dashboard-api.py` — GET /api/sidebar-stats
- `tests/python/test_sidebar_stats.py` (NEW, 3 tests)
- `dashboard/app/components/SidebarStatsWidget.vue` (NEW)
- `dashboard/app/layouts/default.vue` — mount widget above bottom nav

## [3.21.0] - 2026-05-26

### Added (Compare two agents side-by-side — PR87c)

Select exactly two rows on `/agents`, click **Compare** in the bulk
action bar, and you land on `/agents/compare?ids=a,b` — a 2-column
diff view of identity, DNA, Big Five, expertise, frameworks, and
primary mental models. Differences get a yellow-tinted border so the
delta jumps out.

### Files changed

- `dashboard/app/pages/agents/compare.vue` (NEW)
- `dashboard/app/pages/agents/index.vue` — Compare button + handler

## [3.20.0] - 2026-05-26

### Added (Persona Markdown import — PR87b)

The /personas page gains an "Import .md" button next to "New Persona".
Operator picks one or more `.md` files; the dashboard reads them,
posts to a new endpoint, and creates personas from the YAML
frontmatter.

### Backend

- `POST /api/personas/import` (NEW) — accepts
  `{files: [{name, content}]}`, reuses
  `ObsidianPersonaStore._parse_frontmatter` +
  `_frontmatter_to_persona`. Files without `type: persona` are
  rejected with an explicit error. Returns
  `{imported, failed, results}`. 8 unit tests.

### Frontend

- `personas/index.vue` — Import button + hidden multi-file input
  (`accept=".md,text/markdown"`). `FileReader`-based bulk parse.
  Single summary toast.

### Files changed

- `scripts/dashboard-api.py` — POST /api/personas/import
- `tests/python/test_personas_import.py` (NEW, 8 tests)
- `dashboard/app/pages/personas/index.vue` — Import button + handler

## [3.19.0] - 2026-05-26

### Added (DNA filters on /agents — PR87a)

`/agents` filter bar gains two new selects:

- **DISC** — all / D / I / S / C (filters by primary DISC letter)
- **MBTI group** — all / Analysts (NT) / Diplomats (NF) / Sentinels
  (S__J) / Explorers (S__P)

Both stack with the existing department + tier + favourites filters
and the search input. Pagination resets to page 1 when any filter
changes. The MBTI grouping table mirrors the one used on /personas
for consistency.

### Files changed

- `dashboard/app/pages/agents/index.vue` — two new selects + 2 refs +
  MBTI grouping map + computed predicate extensions

## [3.18.0] - 2026-05-26

### Added (Markdown bio field — PR86d)

Agents and personas gain a free-text Markdown bio field with a
live Edit / Preview tabbed editor and a rendered Bio section on the
detail pages.

### Backend

- `Persona` Pydantic model gains `bio_md: str = ""`.
- Agent YAML PUT (`PUT /api/agents/{id}`) now accepts and writes a
  `bio_md` field.
- Persona PUT (`PUT /api/personas/{id}`) passes `bio_md` through the
  Persona constructor.
- Existing YAML / JSON files without the field continue to load —
  `bio_md` defaults to empty.

### Frontend

- `dashboard/app/components/MarkdownEditor.vue` (NEW) — tabbed
  Edit / Preview component. Edit is a monospace UTextarea; Preview
  renders via `marked` (GFM + line breaks).
- `AgentEditDrawer` and the persona edit slideover gain a new
  "Bio (Markdown)" section using the editor.
- Agent + persona detail pages render the bio as a styled prose
  block (with Tailwind typography) above the existing tabs / sections.
- `marked@^15.0.0` added to the dashboard deps.

### Why

- Operators want a place to drop voice samples, internal notes,
  context about source material, and personal references — none of
  which fit in the structured DNA / expertise lists.
- Markdown keeps the field structured enough for the Obsidian export
  to copy verbatim into the vault file.

### Files changed

- `core/personas/schema.py` — `bio_md` field
- `scripts/dashboard-api.py` — PUT routes accept `bio_md`
- `dashboard/package.json` — `marked@^15.0.0`
- `dashboard/app/components/MarkdownEditor.vue` (NEW)
- `dashboard/app/components/AgentEditDrawer.vue` — Bio section
- `dashboard/app/pages/agents/[id].vue` — bio render + form wiring
- `dashboard/app/pages/personas/[id].vue` — bio render + form wiring

## [3.17.0] - 2026-05-26

### Added (Export agent profile to Obsidian — PR86c)

Personas have been writing themselves into the Obsidian vault since
v2.x. Agents finally get the same treatment.

### Backend

- `core/agents/obsidian_export.py` (NEW) — provider-agnostic module
  with `export_agent_to_vault(agent)`. Renders the agent dict as
  Markdown with YAML frontmatter (`type: agent`, `id`, `name`, `role`,
  `department`, `tier`, `model`) and sections for Behavioural DNA,
  Expertise, Mental Models, Communication, Linked Personas. Writes
  atomically (`tmp + replace`) to `<vault>/Agents/<id>.md`. 9 unit
  tests.
- `POST /api/agents/{id}/export` — thin endpoint wrapping the module.
  Returns `{exported, path, vault_path}` or `{error}` if the vault is
  not configured.

### Frontend

- `agents/[id].vue` hero gains an "Export" button (between the star
  and Edit). Loading state + toast confirms the relative vault path
  on success.

### Why

- YAML files stay the source of truth, but the operator gets a
  human-readable artifact in their vault for cross-linking with
  notes, projects, and personas.
- Linked personas render as `[[id]]` wikilinks so the vault graph
  surfaces the agent ↔ persona dependency naturally.

### Files changed

- `core/agents/obsidian_export.py` (NEW)
- `tests/python/test_agent_obsidian_export.py` (NEW, 9 tests)
- `scripts/dashboard-api.py` — POST /api/agents/{id}/export
- `dashboard/app/pages/agents/[id].vue` — Export button + handler

## [3.16.0] - 2026-05-26

### Added (Per-agent activity attribution — PR86b)

The cost telemetry has long supported a category field
(`subagent:<dept>`). PR86b finishes the convention: orchestrators may
now set `ARKA_CALL_CATEGORY=subagent:<dept>:<agent_id>` to record
**per-agent** spend on top of the existing dept aggregation.

### Backend

- `core/runtime/llm_provider.py` — `_current_category` docstring now
  documents the extended `subagent:<dept>:<agent_id>` form.
- `GET /api/agents/{id}/activity-strip` — parses both `subagent:<dept>`
  AND `subagent:<dept>:<agent_id>` categories. When per-agent telemetry
  exists for the queried agent, the response prefers it and includes
  `scope: "agent"`. Otherwise scope falls back to `"department"` —
  fully backward-compatible with all prior callers.
- `GET /api/agents/{id}/activity` (NEW) — alias for the strip route
  with the same payload shape.

### Frontend

- `ActivityStrip` interface gains `scope: 'agent' | 'department'`.
- Strip label switches between `30D ACTIVITY (AGENT)` and `(DEPT)`.

### Migration

- Existing `subagent:<dept>` rows keep accumulating into dept totals.
- Per-agent: set `ARKA_CALL_CATEGORY=subagent:<dept>:<agent_id>` and
  the next strip request surfaces `scope: "agent"`.

### Files changed

- `core/runtime/llm_provider.py` — docstring
- `scripts/dashboard-api.py` — parser + alias endpoint
- `tests/python/test_agent_activity_strip.py` — 2 new tests
- `dashboard/app/pages/agents/[id].vue` — scope label

## [3.15.0] - 2026-05-26

### Added (Favorites for agents + personas — PR86a)

Star agents and personas across sessions. Filter tables to favourites
only. State lives in `~/.arkaos/favorites.json` — no server, no auth.

### Backend

- `core/favorites.py` (NEW) — JSON-backed store at
  `~/.arkaos/favorites.json`. Atomic writes (`.tmp + replace`).
  Graceful on missing / corrupt file. Public API: `list_favorites`,
  `is_favorite`, `toggle`, `set_favorite`. 10 unit tests.
- `GET /api/favorites` — returns `{agents, personas}`.
- `POST /api/favorites/{kind}/{item_id}` — toggles; returns
  `{kind, id, favorited}`.

### Frontend

- `useFavorites()` composable (createSharedComposable) — shared state
  + `load`, `toggle`, `isAgentFavorite`, `isPersonaFavorite`. Single
  source of truth across the dashboard.
- `agents/index.vue` — new favourite column with star toggle, plus
  "Favorites" pill in the filter bar that narrows the table to
  starred rows.
- `personas/index.vue` — same.
- `agents/[id].vue` hero — star button next to Edit.
- `personas/[id].vue` hero — star button next to Clone / Edit.

### Files changed

- `core/favorites.py` (NEW)
- `tests/python/test_favorites.py` (NEW, 10 tests)
- `scripts/dashboard-api.py` — 2 new endpoints
- `dashboard/app/composables/useFavorites.ts` (NEW)
- `dashboard/app/pages/agents/index.vue` — column + filter
- `dashboard/app/pages/personas/index.vue` — column + filter
- `dashboard/app/pages/agents/[id].vue` — hero star
- `dashboard/app/pages/personas/[id].vue` — hero star

## [3.14.0] - 2026-05-26

### Added (Global search palette — PR85d)

Press `/` from anywhere in the dashboard to open a command palette
that searches across agents, personas, departments, and commands in
one debounced fetch. Enter (or click) navigates to the target.

### Backend

- `GET /api/search?q=<query>&limit=<N>` (NEW) — case-insensitive
  substring match across:
  - Agents (name + role + department + id)
  - Personas (name + title + source + mbti + id)
  - Departments (derived from agents)
  - Commands (command + description + department)
- Returns a flat list of `{kind, id, label, sublabel, to}` objects
  ready for the UI to render and route.
- 6 unit tests cover empty query, whitespace, shape invariants,
  limit truncation, case insensitivity, and dept matches.

### Frontend

- `dashboard/app/components/GlobalSearch.vue` (NEW) — UModal +
  UInput + results list with kind-coloured icons and badges.
  Debounced (180 ms) fetch with `AbortController` cancellation so a
  fast typer doesn't queue stale requests.
- `useDashboard()` composable gains `searchOpen` shared state and
  binds `/` to toggle it.
- `KeyboardShortcutsHelp` lists `/` under Actions.
- Layout mounts `<GlobalSearch />` next to the shortcuts help.

### Files changed

- `scripts/dashboard-api.py` — GET /api/search
- `tests/python/test_global_search.py` (NEW, 6 tests)
- `dashboard/app/components/GlobalSearch.vue` (NEW)
- `dashboard/app/composables/useDashboard.ts` — `/` binding + state
- `dashboard/app/components/KeyboardShortcutsHelp.vue` — `/` row
- `dashboard/app/layouts/default.vue` — mount GlobalSearch

## [3.13.0] - 2026-05-26

### Added (Keyboard shortcuts + help overlay — PR85c)

The dashboard already had `g h / g a / g c / g b / g t / g k / g e`
wired through `defineShortcuts`. PR85c finishes the keymap and adds an
overlay so operators can discover it without reading the source.

### New shortcuts

- `g p` → /personas (was missing — fills the obvious gap)
- `g r` → /trash (recycle)
- `g s` → /settings
- `n`  → context-aware new: on /agents → /agents/new, on /personas
        → /personas/new, otherwise /agents/new
- `?`  → toggle the keyboard-shortcuts help modal

### New component

- `dashboard/app/components/KeyboardShortcutsHelp.vue` — UModal listing
  every registered shortcut grouped by Navigation / Actions. Triggered
  by `?` via shared state in the dashboard composable.

### Wiring

- `useDashboard()` composable extended with `contextualNew()`,
  `shortcutsHelpOpen` shared state, and the four new bindings.
- `default.vue` layout now invokes `useDashboard()` to register the
  shortcuts globally and mounts `<KeyboardShortcutsHelp />`.

### Files changed

- `dashboard/app/composables/useDashboard.ts` — keymap + state
- `dashboard/app/components/KeyboardShortcutsHelp.vue` (NEW)
- `dashboard/app/layouts/default.vue` — invoke composable + mount help

## [3.12.0] - 2026-05-26

### Added (Trash + Undo for destructive actions — PR85b)

Deleting an agent, deleting a persona, or moving an agent across
departments is no longer one-shot. Every destructive op now writes a
trash record, and the operator can restore it from `/trash` (newly
added route) or inline from the toast.

### Backend

- `core/trash.py` (NEW) — file-based trash store at `~/.arkaos/trash/`.
  Each entry is two sidecar files: `.payload` (content, optional) and
  `.meta.json` (kind, item_id, paths, timestamp). Bounded by
  `MAX_ENTRIES=50` — older entries are pruned on every write.
- `record_deletion`, `record_move`, `list_trash`, `restore`, `purge`.
- Restore semantics: `agent-delete` / `persona-delete` recreate the
  file at `original_path` (refuses overwrite), `agent-move` moves the
  YAML back AND rewrites the `department:` field.
- Hooked into:
  - `DELETE /api/agents/{id}` — writes trash + returns `trash_id`
  - `POST /api/agents/{id}/move` — same
  - `DELETE /api/personas/{id}` — best-effort capture from
    `PersonaManager.get()`
- New endpoints:
  - `GET /api/trash?limit=N`
  - `POST /api/trash/{id}/restore`
  - `DELETE /api/trash/{id}` (purge without restore)
- 10 unit tests cover record + scan + restore + purge + prune + the
  overwrite-refusal invariant.

### Frontend

- `dashboard/app/pages/trash.vue` (NEW) — listing with Restore +
  Discard per entry, relative timestamps, kind-coloured badges.
- Sidebar nav gains a Trash link (next to Settings).
- Bulk delete + bulk move toasts on `/agents` and bulk delete on
  `/personas` now carry an inline **Undo** action that fan-outs to
  the restore endpoint for every captured `trash_id`.
- `undoTrashIds` helper on both pages.

### Safety

- Restore refuses to overwrite an existing file at the target path.
- Trash entries cap at 50 — anything older is pruned automatically.
- Tier 0 deletion is still blocked at the source endpoint, so trash
  never contains C-Suite agents.

### Files changed

- `core/trash.py` (NEW)
- `tests/python/test_trash.py` (NEW, 10 tests)
- `scripts/dashboard-api.py` — wire trash + 3 new endpoints
- `dashboard/app/pages/trash.vue` (NEW)
- `dashboard/app/layouts/default.vue` — sidebar Trash link
- `dashboard/app/pages/agents/index.vue` — Undo action + helper
- `dashboard/app/pages/personas/index.vue` — Undo action + helper

## [3.11.0] - 2026-05-26

### Added (Clone Persona → Agent UI — PR85a)

POST /api/personas/{id}/clone has been a backend endpoint forever, but
the dashboard had no way to drive it. PR85a adds the UI:

- "Clone to Agent" button in the persona detail hero, next to Edit
- `PersonaCloneDialog.vue` (NEW) — UModal with department + tier
  pickers
- On success, navigates to /agents/{new_agent_id}
- Toast confirms with both names

The agent inherits the persona's behavioural DNA, mental models,
expertise, and frameworks. Operator can then run the PR84a Rewrite
flow if they want to specialise it further.

### Files changed

- `dashboard/app/components/PersonaCloneDialog.vue` (NEW)
- `dashboard/app/pages/personas/[id].vue` — button + dialog mount

## [3.10.0] - 2026-05-26

### Added (Dashboard home extras: top departments + recent personas — PR84d)

The home page (`/`) command-center grows two new cards above the
Projects + Incidents row, giving the operator a one-glance summary
of where spend is going and what's been added to the persona library.

### Backend

- `GET /api/overview/command-center` payload extended with two new
  keys (existing keys untouched):
  - `top_departments_30d` — top 5 departments by 30d LLM spend
    (sorted desc by `cost_usd`)
  - `recent_personas` — 5 most recently created personas (union of
    JSON store + Obsidian vault, sorted desc by `created_at`)
- New helpers `_top_departments_by_cost` and `_recent_personas`
  isolated from the route handler for testability.
- 6 unit tests cover the helpers + the payload shape.

### Frontend

- `dashboard/app/pages/index.vue` — new row above the existing
  Projects + Incidents grid with two columns:
  - **Top departments (30d)**: ranked list with calls + $ cost per dept
  - **Recent personas**: clickable cards (link to `/personas/{id}`)
    with MBTI badge + Obsidian source pill
- `CommandCenterPayload` extended with `TopDeptRow` and
  `RecentPersonaRow` interfaces for type safety.

### Files changed

- `scripts/dashboard-api.py` — payload + 2 helpers
- `tests/python/test_command_center_extras.py` (NEW, 6 tests)
- `dashboard/app/pages/index.vue` — new row + types

## [3.9.0] - 2026-05-26

### Added (Persona Auto-fill empty lists — PR84c)

The persona edit slideover gains an "Auto-fill empties" button in the
header. One click fans out to `/api/personas/suggest` for every list
that's currently empty and writes the LLM output back into the draft.

Targets all five list fields:
- mental_models
- expertise_domains
- frameworks
- key_quotes
- communication.avoid

### Behaviour

- Only fields with zero items are filled — never overwrites operator
  input.
- If every list already has items, the toast says "No empty lists" and
  nothing fires.
- Parallel fan-out via `Promise.allSettled` so one slow/failed field
  doesn't block the rest.
- Final toast: "Filled N lists via <provider>".
- `markDirty()` so the Save button activates.

### Why

- Operators no longer click Suggest 3-5 times to bootstrap a fresh
  persona — one button does the whole row.
- Pairs with PR82c (per-field Suggest) which remains available for
  expanding lists that already have items.

### Files changed

- `dashboard/app/pages/personas/[id].vue` — autofillEmpties + header
  button

## [3.8.0] - 2026-05-26

### Added (Bulk move department in /agents — PR84b)

The /agents bulk action bar gains a "Move to..." dropdown next to
Delete. Pick a target department, confirm, and every selected agent's
YAML moves across `departments/<src>/agents/` → `departments/<dst>/
agents/` with the `department:` field rewritten to match.

### Backend

- `POST /api/agents/{agent_id}/move` (NEW) — atomic YAML rewrite
  + filesystem rename. Refuses unknown target dept, missing source,
  Tier 0 agents, and collisions at the destination. 6 unit tests
  covering all error paths + the happy path.

### Frontend

- `agents/index.vue` — UDropdownMenu listing all 16 departments next
  to Delete in the bulk action bar. ConfirmDialog before fan-out.
  Parallel POSTs via `Promise.allSettled`; toast summarises success /
  partial / total failure.

### Safety

- Same Tier 0 protection as the delete endpoint.
- Collision detection prevents accidental overwrite of a same-id
  agent that already lives in the target dept.
- All operations atomic per-file (tmp + replace pattern).

### Files changed

- `scripts/dashboard-api.py` — POST /api/agents/{id}/move
- `tests/python/test_agent_move.py` (NEW, 6 tests)
- `dashboard/app/pages/agents/index.vue` — Move dropdown + handler

## [3.7.0] - 2026-05-26

### Added (Rewrite from description in AgentEditDrawer — PR84a)

The agent edit drawer gains a collapsible "Rewrite from description"
card at the top. Paste a new description, click Rewrite, and the
expertise / mental models / frameworks / communication blocks
regenerate from the LLM. Identity (name / role / department) and
behavioural DNA stay untouched.

Reuses the existing `POST /api/agents/draft` endpoint from PR82b —
no new backend.

### Why

- Operators no longer have to expand each list field one item at a
  time when overhauling an agent's profile.
- Pairs with PR82b: that draft path is for CREATE, this is for EDIT.

### Safety

- Identity, department, and behavioural DNA are NEVER mutated by
  Rewrite. The function only writes the safe-to-edit fields.
- Card is collapsed by default — invisible unless the operator opens it.
- Same validation as PR82b: description must be ≥ 20 chars.
- `markDirty()` fires so the Save button activates.

### Files changed

- `dashboard/app/components/AgentEditDrawer.vue` — Rewrite card + handler

## [3.6.1] - 2026-05-26

### Fixed (Persona row click → /personas/undefined — hotfix)

`personas/index.vue` was destructuring the UTable `@select` payload as
the raw Persona object, but UTable passes `{ original, getValue, ... }`
— so `row.id` was `undefined` and the row navigated to
`/personas/undefined`. The arrow button worked because it correctly
used `row.original.id`.

Changed `@select="(row: Persona) => goToPersona(row.id)"` to
`@select="(row: { original: Persona }) => goToPersona(row.original.id)"`
to match the actions-cell handler.

## [3.6.0] - 2026-05-26

### Added (Agent activity strip on /agents/{id} hero — PR83d)

The agent detail page gains a one-line activity strip below the stats
row: 30d calls + cost + tokens + last-used + dept rank. Operator can
see at a glance whether the agent's department is actively used and
where it sits in the cost ranking.

### Backend

- `GET /api/agents/{agent_id}/activity-strip` (NEW) — compact payload
  derived from PR47 telemetry. Returns `period`, `department`, `calls`,
  `cost_usd`, `tokens_in`, `tokens_out`, `last_used` (most recent
  telemetry ts for this dept), `dept_rank` (1-based, by 30d cost),
  `dept_count`. Defaults to 30-day period. Per-agent attribution
  isn't tracked yet (telemetry tags at dept level via
  `subagent:<dept>`) so the strip is dept-level by design.
- 6 unit tests cover error path + payload shape + period override
  + invalid-period fallback + rank invariants.

### Frontend

- `agents/[id].vue` — new `<section>` below the stats row showing
  6 items in a single-line flex row:
  - icon + "30D ACTIVITY (DEPT)" label
  - Calls (number)
  - Cost (formatted via existing `formatCost`)
  - Tokens (in / out)
  - Last used (relative — uses new `formatRelative` helper)
  - Dept rank badge (primary tint for top-3)
- The strip hides itself when the endpoint returns no data, so the
  detail page degrades gracefully on a fresh install.

### Files changed

- `scripts/dashboard-api.py` — GET /api/agents/{id}/activity-strip
- `tests/python/test_agent_activity_strip.py` (NEW, 6 tests)
- `dashboard/app/pages/agents/[id].vue` — activity strip section
  + `formatRelative` helper

## [3.5.0] - 2026-05-26

### Added (Single-string AI fill — PR83c)

The PR81 ✨ Suggest mechanism handles list fields by APPENDING items.
Tone, preferred format, and language are single strings, so they need
REPLACE semantics. PR83c builds a sibling module + endpoints + buttons.

### Backend

- `core/agents/string_suggester.py` (NEW) — provider-agnostic
  `suggest_string_field(field, context, provider)`. Supports `tone`,
  `preferred_format`, `language`. Field-specific length limits (60/80/
  20 chars). Strips fences, surrounding quotes, leading bullets, and
  numbering from the LLM output. 17 unit tests.
- `POST /api/agents/suggest-string` + `POST /api/personas/suggest-string`
  — share `_do_string_suggest` helper.

### Frontend

- **AgentEditDrawer**: ✨ Generate buttons next to Tone + Preferred
  format.
- **agents/new.vue**: same two buttons. Refuses to fire until name +
  role are filled.
- **personas/[id].vue** edit slideover: ✨ Generate next to Tone.
  (Persona slideover doesn't expose preferred_format yet — that's a
  separate ask.)

### Semantics

- Unlike list Suggest (APPEND), string Generate REPLACES the field
  value. Current value is passed to the LLM as a "do not repeat
  verbatim" hint.
- One button in flight at a time per form (`suggestingString` ref).
- Each form has both `suggestingField` (list) and `suggestingString`
  (string) refs so they don't lock each other.

### Files changed

- `core/agents/string_suggester.py` (NEW)
- `tests/python/test_string_suggester.py` (NEW, 17 tests)
- `scripts/dashboard-api.py` — 2 new endpoints + helper
- `dashboard/app/components/AgentEditDrawer.vue` — 2 Generate buttons
- `dashboard/app/pages/agents/new.vue` — 2 Generate buttons
- `dashboard/app/pages/personas/[id].vue` — 1 Generate button (tone)

## [3.4.0] - 2026-05-26

### Added (Bulk actions on /agents and /personas tables — PR83b)

Operators can now select multiple rows in either table and delete them
in one click. Selection state lives in the page; the floating action
bar slides in from below as soon as anything is checked.

### Backend

- `DELETE /api/agents/{agent_id}` (NEW) — atomic YAML unlink. Refuses
  to delete **Tier 0 (C-Suite)** agents to keep the constitutional
  fixtures intact. Resolves the YAML file via the cached registry
  AND a filesystem scan, so freshly-created agents (which aren't in
  the registry yet) can also be deleted. 3 unit tests.
- `_resolve_agent_yaml` + `_agent_tier_from_yaml` helpers extracted.

### Frontend

- `agents/index.vue` — first column is now a UCheckbox. Header
  checkbox toggles all-visible selection. Floating action bar at
  bottom shows count + Clear + Delete. Confirm dialog uses the
  PR75 `useConfirmDialog` with `variant: 'danger'`.
- `personas/index.vue` — same pattern using the existing persona
  DELETE endpoint.
- Bulk delete fires N parallel DELETEs via `Promise.allSettled` so
  one failure doesn't block the rest. Toast summarises success /
  partial failure / total failure.

### Safety

- Tier 0 protection enforced server-side, surfaced to the operator
  in the toast: "N skipped (Tier 0 or missing)".
- Confirm dialog is `variant: 'danger'` and shows the exact count.
- Selection clears on completion.

### Files changed

- `scripts/dashboard-api.py` — DELETE /api/agents/{id} + helpers
- `tests/python/test_agent_delete.py` (NEW, 3 tests)
- `dashboard/app/pages/agents/index.vue` — selection + bar
- `dashboard/app/pages/personas/index.vue` — selection + bar

## [3.3.0] - 2026-05-26

### Added (Persona draft from description — PR83a)

Persona creation no longer requires indexed content. PersonaWizard
Step 1 gains a 3-mode picker (Ingest sources / Existing chunks /
From description), and the description path goes straight to a draft
via a new dedicated endpoint.

### Backend

- `core/personas/description_drafter.py` (NEW) — provider-agnostic
  `draft_persona_from_description(description, name, source_label,
  provider)`. Reuses the existing `_PERSONA_SYSTEM_PROMPT` and
  `_extract_json_object` from the vector builder so the resulting
  Persona is interchangeable. Validates description ≥ 20 chars,
  non-empty name, schema match. 12 unit tests.
- `POST /api/personas/draft` — wraps the drafter. Returns
  `{persona, provider_name}`. `PersonaDraftError` surfaces as an
  error payload. Body shape:
  `{description, name, source_label?}`.

### Frontend

- `PersonaWizard.vue` — Step 1 redesigned with three mode cards:
  - **Ingest sources** — original flow (URLs → background jobs)
  - **Existing chunks** — was `skipIngest`, now first-class
  - **From description** — new path, no vector DB needed
- The textarea / source list swaps based on mode; CTA label adapts.
- `runDescriptionBuild()` calls `/api/personas/draft` and routes
  straight to Step 4 (Review & save) bypassing chunks-used UI.

### Why this matters

- Operators can sketch a synthetic archetype in 30 seconds
- No vector-DB dependency for the quick-draft path
- Pairs with PR82c so the operator can then click Suggest with AI
  to expand each field after the draft lands

### Files changed

- `core/personas/description_drafter.py` (NEW)
- `tests/python/test_persona_description_drafter.py` (NEW, 12 tests)
- `scripts/dashboard-api.py` — POST /api/personas/draft
- `dashboard/app/components/PersonaWizard.vue` — 3-mode picker

## [3.2.0] - 2026-05-26

### Added (Extended suggester + persona Avoid/Key quotes editable — PR82c)

The ✨ Suggest with AI buttons now cover two more list fields, and
persona edit gains two long-requested editable sections.

### Suggester extended

- `core/agents/field_suggester.py` — `_VALID_FIELDS` now includes:
  - `communication_avoid` — phrases the profile would never say
  - `key_quotes` — verbatim/paraphrased sentences (persona only)
- Per-field length hints: short items (2-5 words) for mental models /
  frameworks / expertise, mid-length (2-6 words) for avoid, full
  sentences (8-25 words) for key quotes.
- 5 new unit tests (23 total) covering the new fields + assertions
  that legacy fields still get the original length hint.

### Frontend wiring

- `AgentEditDrawer.vue` — Suggest button next to the "Avoid (phrases)"
  field.
- `agents/new.vue` — same Suggest button on the create form.
- `personas/[id].vue` edit slideover gains two NEW editable sections:
  - **Avoid (phrases)** — CSV input + Suggest button
  - **Key quotes** — UTextarea (one per line) + Suggest button
  Both write through the existing `PUT /api/personas/{id}` atomic save.

### Types

- `Persona` interface in `dashboard/app/types/index.d.ts` now declares
  `key_quotes?: string[]` and `communication.avoid?: string[]` so the
  editable form fields are type-safe.

### Files changed

- `core/agents/field_suggester.py` — extended fields + length hints
- `tests/python/test_field_suggester.py` — 5 new tests
- `dashboard/app/components/AgentEditDrawer.vue` — avoid Suggest
- `dashboard/app/pages/agents/new.vue` — avoid Suggest
- `dashboard/app/pages/personas/[id].vue` — Avoid + Key quotes sections
- `dashboard/app/types/index.d.ts` — Persona type extension

## [3.1.0] - 2026-05-26

### Added (AI draft from description on /agents/new — PR82b)

The /agents/new form now has a "Draft with AI" card at the top: paste a
free-text description of the agent, click Generate, and the LLM fills
in DISC primary/secondary, Enneagram type+wing, MBTI, all five Big Five
axes, expertise domains + frameworks + depth + years, mental models,
and the whole communication block.

The operator still owns the create — every field is editable after the
draft is applied, and Save only fires on explicit click.

### New backend

- `core/agents/draft_builder.py` (NEW) — provider-agnostic module with
  `draft_agent(description, name, role, department, tier, provider)`.
  Validates the LLM output before returning: DISC primary ≠ secondary,
  DISC letters in {D,I,S,C}, Big Five 0..100, `behavioral_dna` block
  present. Bad LLM output surfaces as a `DraftError` instead of
  silently breaking the form.
- `POST /api/agents/draft` — thin endpoint that wraps `draft_agent`.
  Defaults tier to 2 on bad input. `LLMUnavailable` is converted to
  `DraftError` and surfaces as a toast.
- 13 new unit tests cover JSON parsing, fence stripping, prompt
  composition, validation rules (DISC equality, invalid letters, out
  -of-range Big Five), and provider failure.

### New frontend

- `dashboard/app/pages/agents/new.vue` — primary-tinted "Draft with AI"
  card above the form with a 3-row UTextarea + Generate button.
  Button refuses to run on descriptions < 20 chars. On success the
  draft is applied to every field that the LLM filled, untouched fields
  keep their defaults. Toast confirms the provider name.

### Why this matters

- One-click agent creation for non-technical operators
- Operators no longer have to think about DISC theory or Enneagram
  numbers to onboard a new agent — they describe the human and the
  system does the framework translation
- Pairs with the PR81 ✨ Suggest buttons on the list fields so even
  after the draft, individual lists can be expanded with one more
  click

### Files changed

- `core/agents/draft_builder.py` (NEW)
- `tests/python/test_agent_draft_builder.py` (NEW, 13 tests)
- `scripts/dashboard-api.py` — POST /api/agents/draft
- `dashboard/app/pages/agents/new.vue` — Draft card + applyDraft logic

## [3.0.0] - 2026-05-26

### Added (Agent create flow — PR82a)

ArkaOS finally has a "New Agent" path that doesn't require editing
YAML by hand. Click "New Agent" from `/agents`, fill the form, click
Create. Done.

The version bump to 3.0.0 marks the milestone: every agent and persona
lifecycle action (create / read / update / delete) is now in the
dashboard with AI assistance built in.

### New backend

- `POST /api/agents` — creates a new agent YAML file under
  `departments/{dept}/agents/{slug}.yaml`. Refuses to overwrite
  existing files. 16 unit tests cover slug rules, default
  composition, tier-based model selection, DISC/MBTI normalisation,
  and collision handling.
- Helpers: `_do_agent_create`, `_agent_slugify`, `_build_agent_yaml`.

### New frontend

- `dashboard/app/pages/agents/new.vue` — single-page form with four
  sections (Identity / Behavioural DNA / Knowledge / Communication)
  plus Linked Personas. Sensible defaults pre-fill the DNA so
  non-technical operators don't face a wall of blanks.
- ✨ Suggest with AI buttons (from PR81) are wired on the three
  list fields. They refuse to run until name + role are filled —
  AI needs the basics to make useful suggestions.
- `dashboard/app/pages/agents/index.vue` — "New Agent" button added
  to the navbar `#right` slot, mirroring the personas pattern.

### Validation

- Save is disabled until name + role + department are non-empty AND
  DISC primary ≠ DISC secondary (matches the Pydantic schema rule).
- On error the toast surfaces the backend message; the form is
  preserved.

### Files changed

- `scripts/dashboard-api.py` — POST /api/agents + helpers
- `tests/python/test_agent_create.py` (NEW, 16 tests)
- `dashboard/app/pages/agents/new.vue` (NEW)
- `dashboard/app/pages/agents/index.vue` — New Agent button

## [2.99.0] - 2026-05-26

### Added (AI-assist on agent + persona edit forms — PR81)

Non-technical operators can now click ✨ Suggest with AI next to list
fields to have the configured LLM propose new items that fit the
entity's existing context — no more staring at an empty comma-separated
input wondering what mental models a "growth strategist" should have.

### New backend

- `core/agents/field_suggester.py` — provider-agnostic module with
  `suggest_field(field, context, count, provider)`. Field must be one of
  `mental_models`, `frameworks`, `expertise_domains`. Context accepts
  `name`, `role` / `title`, `department`, and `current` (existing items
  excluded from the suggestion set). Returns `SuggestionResult` with the
  cleaned list and the provider name that served it.
- `POST /api/agents/suggest` — wraps `suggest_field` for the agent edit
  drawer. Reads context from the live agent.
- `POST /api/personas/suggest` — same for personas (uses `title` in lieu
  of `role`).

### New frontend

- `AgentEditDrawer.vue` — ✨ Suggest with AI button next to:
  - Mental models (primary)
  - Expertise domains
  - Frameworks
  Buttons are mutually exclusive (one in-flight at a time), show a
  spinner, and append deduped suggestions to the field. Toast confirms
  count + provider name. Triggers the dirty flag.
- `personas/[id].vue` edit slideover — same three buttons wired to the
  persona endpoint.

### Safety

- LLM prompt explicitly forbids duplicating items already in `current`.
- Backend AND frontend dedupe (case-insensitive) against the current
  list before mutating the draft.
- `count` is clamped to `[1, 12]` server-side.
- `LLMUnavailable` is converted to a `SuggestionError` and surfaces as
  a toast — the form never breaks.
- 18 new unit tests cover JSON parsing, fences, count clamping,
  deduplication, prompt construction, and provider-failure fallback.

### Files changed

- `core/agents/field_suggester.py` (NEW)
- `tests/python/test_field_suggester.py` (NEW, 18 tests)
- `scripts/dashboard-api.py` — 2 new endpoints + shared helper
- `dashboard/app/components/AgentEditDrawer.vue` — Suggest buttons
- `dashboard/app/pages/personas/[id].vue` — Suggest buttons

## [2.98.0] - 2026-05-26

### Fixed (Dead "New Persona" link — PR80)

PR78 moved the "New Persona" CTA into the personas table header but
pointed it at `/personas/new`, a route that didn't exist. Result: the
button 404'd. PR80 plugs in the missing route.

### Added

- `dashboard/app/pages/personas/new.vue` — wraps the existing
  `PersonaWizard` component (4-step AI-assisted flow: Sources → Ingest
  → Build → Save). The page itself is a thin hosting shell:
  - `@completed(persona)` → toast + `navigateTo('/personas/{id}')`
  - `@cancelled` → `navigateTo('/personas')`
- Back arrow in the navbar leading slot.
- "AI-assisted" badge in the navbar trailing slot to telegraph the
  wizard nature of the route.

### Files changed

- `dashboard/app/pages/personas/new.vue` (NEW)

## [2.97.0] - 2026-05-26

### Fixed (Detail pages readability — PR79)

- **Agent + Persona detail pages**: bumped tiny `text-xs uppercase tracking-wider`
  section labels to `text-sm uppercase tracking-wide` for readability. The
  previous size was unreadable at standard viewport zoom, especially the
  stats-row labels (LINKED AGENTS, MENTAL MODELS, EXPERTISE DOMAINS,
  FRAMEWORKS) and the per-card tab section headers.
- **Knowledge tab badges**: bumped `size="xs"` UBadge instances to `size="sm"`
  on `/personas/{id}` and `/agents/{id}`. Operator-flagged: persona detail
  with 31 expertise badges was effectively a wall of unreadable text.
- **Hero badges**: same bump applied to source/MBTI/DISC chips in the hero
  block so they match the new label scale.

No behaviour change — purely a CSS readability fix. Same edit applied to
both detail pages to keep the agents / personas UX consistent.

### Files changed

- `dashboard/app/pages/personas/[id].vue` — replace_all `text-xs ... tracking-wider` → `text-sm ... tracking-wide`; `size="xs"` → `size="sm"` on UBadge
- `dashboard/app/pages/agents/[id].vue` — same edits for parity

## [2.96.0] - 2026-05-26

### Changed (Personas → table list + dedicated detail page — PR78)

Operator correction on PR77: "quando disse as personas iguais aos
agents era ter a table no index e ter uma pagina semelhante, não o
que fizeste". PR78 fixes the mistake — personas now match the agents
UX exactly.

#### Replaced
- **`personas.vue` (card grid + drawer)** → moved into
  `personas/index.vue` (TABLE) following the `agents/index.vue`
  pattern.
- **`PersonaDetailDrawer.vue`** — deleted. The drawer-everywhere
  pattern is gone; navigation now uses dedicated routes.

#### New
- **`personas/index.vue`** — sortable / filterable table:
  - Columns: Name · Title · Source · MBTI · DISC · Expertise · Agents · ▶
  - Filters: search (name/title/source/expertise) + MBTI group
    (Analysts/Diplomats/Sentinels/Explorers) + source store
    (Obsidian / JSON)
  - Header badge: total count + "Obsidian" pill when the vault is
    wired
  - "New Persona" button → `/personas/new` (route for AI builder
    wizard, lands in PR79)
- **`personas/[id].vue`** — dedicated detail page mirroring the
  agent detail layout:
  - Hero with MBTI-grouping gradient + initials avatar + name +
    tagline + source/MBTI/DISC badges + obsidian path
  - Stats row (4 cards): linked agents · mental models · expertise
    domains · frameworks
  - 4 tabs (default `dna`): **DNA** (MBTI/Enneagram/DISC/Big-Five
    bars) · **Communication** (tone, vocab) · **Knowledge** (mental
    models, expertise, frameworks, key quotes) · **Linked Agents**
    (clickable cards → /agents/{id})
  - Edit (✏️) and Delete (🗑️) actions in the hero. Edit opens a
    USlideover with full form (same fields as the old drawer).

### Test coverage
- Vue typecheck clean across both new pages
- Full Python suite: 3824/3824 passing (no backend changes)
- Preflight: `all_passed: True`

## [2.95.0] - 2026-05-26

### Added (Personas page modernization — PR77)

Same visual treatment landed on the agent detail page (PR76),
applied to personas.

List cards:
- Gradient header per card by MBTI grouping (Analysts blue,
  Diplomats emerald, Sentinels amber, Explorers rose)
- Initials avatar inside gradient header
- "N agents" badge when persona is linked to agent YAMLs
- Cards now use rounded-2xl div for cleaner gradient bleed

Detail drawer:
- Gradient hero matching list tint, size-14 avatar, 2xl name
- Source badge + MBTI pill + linked-agent count in hero
- Linked agents section (clickable pills → /agents/{id}) in read mode

Backend:
- GET /api/personas/usage — reverse lookup walking agent YAMLs,
  returns by_persona with agent_count + agent_ids per persona.
  Defensive on missing/malformed YAMLs.

### Test coverage
- 6 new test_personas_usage_api.py cases
- Vue typecheck clean
- Full Python suite: 3824/3824 passing
- Preflight: all_passed=True

## [2.94.0] - 2026-05-26

### Added (Agent detail modernization + edit drawer — PR76)

Closes the operator ask: more modern agent detail page + edit
support for non-technical users.

Visual:
- **Default tab fixed** — UTabs opens with DNA selected
- **Modern hero** — department-tinted gradient + initials avatar +
  full badges row + selectable agent id
- **Stats row** (4 cards): 7d calls / 7d cost / tokens / linked
  personas. Pulls from PR69 /api/agents/activity.
- **16 dept-gradient pairs** so each department always renders the
  same hero tint.

Edit:
- New `AgentEditDrawer.vue` with USlideover + full form:
  identity, mental models, expertise, frameworks, communication,
  linked_personas (multi-select against /api/personas).
- Dirty-state tracking; Save disabled until changes; ConfirmDialog
  (PR75) on close with pending edits.
- Behavioural DNA (DISC/Enneagram/MBTI/Big-Five) intentionally
  locked — changing it silently breaks the agent identity model.

Backend:
- **PUT /api/agents/{id}** — atomic YAML write (.tmp + replace).
  Partial-update body merged on top so unspecified fields preserve.
- **GET /api/agents/{id}** extended with `frameworks`,
  `expertise_domains`, `linked_personas`, `_yaml_path`.

### Test coverage
- Vue typecheck clean
- Full Python suite: 3818/3818 passing
- Preflight: all_passed=True

## [2.93.0] - 2026-05-26

### Changed (Native `window.confirm` → `<ConfirmDialog>` — PR75)

Per the operator's rule: **"não trabalhamos com alerts tem que ser
dialogs sempre"**. The whole dashboard now goes through one canonical
confirm-dialog primitive instead of falling back to the browser's
ugly native prompt.

- **`dashboard/app/components/ConfirmDialog.vue`** — `UModal`-based
  confirm dialog with `title`, `description`, `confirmLabel`,
  `cancelLabel`, and a `variant: 'default' | 'danger'` prop. Per
  the canonical Nuxt UI v4 pattern from
  `ui.nuxt.com/docs/composables/use-overlay`.
- **`dashboard/app/composables/useConfirmDialog.ts`** — `await
  useConfirmDialog()({...})` returns `Promise<boolean>`. Uses
  `useOverlay().create(ConfirmDialog, …).open()` under the hood.

### Migrated call sites (3 of 3)

- `PersonaDetailDrawer.vue::deletePersona` — "Delete persona X"
  with `variant: 'danger'`.
- `PersonaDetailDrawer.vue::closeDrawer` — "Discard unsaved edits?"
  shown only when leaving Edit mode with pending changes.
  Confirm label is `Discard`, cancel is `Keep editing`.
- `knowledge.vue::askDeleteSource` — "Delete every indexed chunk
  from this source?" with the source path in the description.

A grep for `window.confirm` / `window.alert` across `dashboard/app/`
now returns only the documentation comments inside ConfirmDialog +
useConfirmDialog — no live native calls remain.

### Test coverage

- Vue typecheck clean across new component, new composable, and
  all 3 migrated call sites
- Full Python suite: 3818/3818 passing (no backend changes)
- Preflight: `all_passed: True`

## [2.92.0] - 2026-05-26

### Added (Persona detail view + edit — PR74)

- **`PersonaDetailDrawer.vue`** — click any persona card on the list
  to open a side-drawer with **every field** visible: identity,
  full DNA (DISC + Enneagram + MBTI + Big-Five with horizontal
  bars), mental models, expertise, frameworks, key quotes,
  communication style.
- **Edit mode** — ✏️ in the header flips the drawer to an editable
  form: text inputs for identity + free-text, dropdowns for
  MBTI/DISC/vocab, number+range pair for each Big-Five score,
  comma-separated CSV inputs for the list fields. Cancel restores
  cleanly (deep-clone on edit start).
- **Source badge** — every persona shows whether it came from the
  Obsidian vault (`From Obsidian`) or the JSON store, plus the
  vault path so the operator can find the file.
- **Delete from drawer** — explicit confirm; the Obsidian file is
  not auto-deleted (operator removes it from Obsidian manually).

### Backend changes

- **`GET /api/personas/{id}`** now checks the Obsidian vault first
  and surfaces `_source_store` + `_obsidian_path` on the response.
  Previously vault-only personas returned 404; now they resolve.
- **`PUT /api/personas/{id}`** (new) — atomic update across both
  stores. Partial-update bodies are merged on top of the existing
  record so unspecified fields don't get wiped. Returns
  `{ id, updated, json_written, obsidian_path }` so the UI can
  show exactly where the save landed.

### Test coverage

- Vue typecheck clean (new component + edits)
- Full Python suite: 3818/3818 passing
- Preflight: `all_passed: True`

## [2.91.0] - 2026-05-25

### Fixed (SQLite threading + vector-search visibility — PR73)

- **`SQLite objects created in a thread can only be used in that same thread`
  is fixed.** `core/knowledge/vector_store.py` now opens its connection
  with `check_same_thread=False` and serialises writes through a
  per-instance `threading.Lock`. WAL mode is enabled so concurrent
  readers don't block. The bulk-ingest / single-ingest / upload-file
  paths in `scripts/dashboard-api.py` all share a single store
  instance from background workers cleanly.
- **`/api/knowledge/stats` now reports `vec_unavailable_reason`** so
  the dashboard can surface *why* vector search is offline. Common
  reasons:
  - `sqlite-vec package missing` → `pip install sqlite-vec`
  - Python sqlite3 built without extension loading
  - Extension loaded but `CREATE VIRTUAL TABLE vec_chunks` failed
- **Knowledge page** shows the actual reason instead of a generic
  "Unavailable" badge. The hero badge flips from "Vector Off"
  (warning) to "Vector Active" (success) based on a new
  `vectorSearchActive` computed that accepts either the new
  `vec_available` or the legacy `vss_available` flag.

### Added (Personas from Obsidian — PR73)

- **`core/personas/obsidian_store.py`** — new module that reads/writes
  personas as Markdown files under `<vaultPath>/Personas/`. Frontmatter
  schema mirrors the `Persona` Pydantic model (DISC, Enneagram, Big
  Five, MBTI, mental models, expertise, frameworks, key quotes,
  communication). Recognises the legacy `expertise:` alias.
- **`GET /api/personas`** now merges JSON-store personas with the
  Obsidian vault. **Obsidian wins on conflicts** (it's the operator's
  source of truth). Response carries `obsidian_available: bool` so
  the UI can show whether the vault is wired.
- **`POST /api/personas`** also writes the new persona to the vault
  (best-effort — JSON-store success is unaffected by vault write
  failures). Response carries `obsidian_path` when the write succeeded.

### Operator action needed

Run `pip3 install sqlite-vec` once to enable vector search. The
dashboard's Knowledge page will tell you exactly that until you do.

### Test coverage

- 4 new `tests/python/test_vector_store_threading.py` cases:
  background thread can write+search, concurrent writes don't
  corrupt, main thread stays usable after worker, connection
  accepts cross-thread reads
- 16 new `tests/python/test_obsidian_persona_store.py` cases:
  empty vault, missing personas dir, minimal+full frontmatter,
  non-persona-type skip, no-frontmatter skip, legacy `expertise:`
  alias, corrupt YAML, write to personas folder, auto-create
  folder, no-vault → None, overwrites, round trip, availability
- Vue typecheck clean
- Full Python suite: 3818/3818 passing
- Preflight: `all_passed: True`

## [2.90.0] - 2026-05-25

### Added (Global light/dark switch in sidebar header — PR72)

- **`<UColorModeButton />`** mounted in the dashboard sidebar header
  (next to the "ArkaOS" wordmark). Nuxt UI's canonical color-mode
  toggle — flips sun ↔ moon icon, handles SSR via `<ClientOnly>`
  internally, persists the choice through `useColorMode`.
- Visible on **every page** — operators don't have to dive into
  Settings → Theme to flip the appearance.
- **Hidden when sidebar is collapsed** (icon-only mode); the bare
  "A" mark is the only thing showing in that state. The explicit
  3-way picker in Settings → Theme (system / light / dark) stays
  as the deeper preference UI.

### How I picked the component

Researched via `mcp__context7` on `/websites/ui_nuxt` (Nuxt UI's
canonical docs). Two recommended approaches:

1. Drop-in `<UColorModeButton />` (zero config).
2. Custom button using `useColorMode()` with manual sun/moon icon swap.

Went with (1) — it's the documented Nuxt UI primitive, ships ARIA
labels, and stays in sync with `useColorMode.preference` updates
from the Settings page automatically.

### Test coverage

- Vue typecheck clean
- Full Python suite: 3798/3798 passing (no backend changes)
- Preflight: `all_passed: True`

## [2.89.0] - 2026-05-25

### Added (Settings expansion: MCPs / Hooks / Plugins / Theme — PR63b)

Closes the original 10-PR dashboard backlog plus the follow-up
PR63b. Settings now has all 7 sections promised in the audit.

#### Backend

- **`GET /api/settings/mcps`** — merges `~/.claude.json::mcpServers`
  with `~/.claude/skills/arka/mcps/registry.json`. Dedupes by name
  (user-global wins). Detects transport (stdio / http / sse / unknown).
  Handles both dict-shape and list-shape registries. Corrupt JSON
  swallowed.
- **`GET /api/settings/hooks`** — parses `~/.claude/settings.json::hooks`
  into one row per hook type with command paths + timeouts. Surfaces
  `hard_enforcement` flag from the PR19 binding-flow enforcement
  switch. Read-only diagnostics.
- **`GET /api/settings/plugins`** — flattens
  `~/.claude/plugins/installed_plugins.json` into one row per
  `(name, marketplace, version)`. Sorted by marketplace then name.

#### Frontend (`settings.vue`)

- **4 new sections** behind the existing left-nav: MCPs, Hooks,
  Plugins, Theme.
- **MCPs** — each server with source badge (`user-global` /
  `arkaos-registry`), transport pill (stdio / http / sse), command
  preview.
- **Hooks** — per-hook-type group with command + timeout list. A
  primary-tinted banner appears at top when `hardEnforcement` is on.
- **Plugins** — name + marketplace + version + scope + installed-at
  per row. Empty state hints at the `/plugin marketplace add` flow.
- **Theme** — `useColorMode()` picker (System / Light / Dark) with a
  "Currently rendering as ..." footer.

### Test coverage

- 13 new `tests/python/test_settings_sections_api.py` cases:
  - **MCPs (6)**: empty, user-global parse, dedupe with arkaos
    registry, http transport detection, corrupt JSON, list-shape
    registry support
  - **Hooks (4)**: missing file, full block parse, hardEnforcement
    flag surface, corrupt JSON
  - **Plugins (3)**: missing file, marketplace-keyed flatten,
    corrupt JSON
- Vue typecheck clean
- Full Python suite: 3798/3798 passing
- Preflight: `all_passed: True`

### Dashboard UI backlog status — closed

11 PRs shipped: PR62 wizard, PR63 settings, PR64 dashboard-state,
PR65 budget, PR66 command-center, PR67 tasks, PR68 commands,
PR69 agents, PR70 health, PR71 knowledge, PR63b settings full set.

## [2.88.0] - 2026-05-25

### Added (Knowledge page: delete source + match highlight — PR71)

- **`DELETE /api/knowledge/sources?source=<path>`** — removes every
  indexed chunk that came from a given source. Wraps the existing
  `VectorStore.remove_file(source)`; rejects empty / whitespace-only
  `source` so a runaway client can't accidentally request "delete
  everything that has no source". Catches store exceptions inline
  so the endpoint never raises.
- **Delete button per search result** in `knowledge.vue` — trash icon
  next to the score, behind a `window.confirm` so it's not
  accidentally clicked. On success the row disappears immediately
  + stats refresh + toast confirms the deletion count.
- **Match highlight** in search-result previews — query terms are
  wrapped in `<mark class="bg-primary/20 text-primary rounded">`
  with regex special characters escaped and HTML escaped first so
  the `v-html` output stays XSS-safe regardless of what the chunk
  contains.

### Test coverage

- 7 new `tests/python/test_knowledge_delete_source.py` cases:
  empty / whitespace rejection, store-missing, success path with
  count, whitespace-strip on input, store-exception swallowed,
  idempotent zero-delete path.
- Vue typecheck clean
- Full Python suite: 3785/3785 passing
- Preflight: `all_passed: True`

### Dashboard UI backlog status

Original 10-PR audit list now complete: **PR62 wizard, PR63 settings,
PR64 dashboard-state, PR65 budget, PR66 command-center, PR67 tasks
real-time, PR68 commands ▶+★, PR69 agents activity, PR70 health
polish, PR71 knowledge polish.** Next batch (PR63b — Settings MCPs /
Hooks / Plugins / Theme) lands when prioritised.

## [2.87.0] - 2026-05-25

### Added (Health page: auto-refresh + severity + copy-fix — PR70)

- **Backend `/api/health` extended** with three new fields:
  - `severity` on every check — `"fail"` (must-pass) or `"warn"`
    (recommended). `knowledge_db` and `profile` are now warn-only
    so a fresh install doesn't show "blocking failures" for things
    the operator simply hasn't done yet.
  - `failed_blocking` and `warning_count` aggregates so the UI
    can distinguish degraded-but-workable from broken.
  - `ts` ISO timestamp on the response so the UI can show
    "last checked".
  - `healthy` now ignores warnings (only blocking failures break it).
- **Frontend `health.vue` rewritten**:
  - 30 s auto-refresh while the tab is visible (pauses on hide,
    refreshes immediately on resume — `visibilitychange` listener)
  - Last-checked timestamp in the header
  - Severity-aware banner: green (all pass), yellow (warnings only),
    red (blocking failures)
  - Per-check ▶ Copy-fix button when a `fix` command is present
    (clipboard write + check-icon confirmation for 1.5 s)
  - Per-check row colour reflects severity (warn = yellow tint,
    fail = red tint)

### Test coverage

- 9 new `tests/python/test_health_api.py` cases:
  - `ts` is ISO with timezone
  - Aggregate fields exist (`failed_blocking`, `warning_count`, `healthy`)
  - Every check carries a `severity` ∈ {`fail`, `warn`}
  - Warn checks don't count as blocking; `warning_count` is correct
  - `healthy` iff no blocking failures (warnings tolerated)
  - `knowledge_db` + `profile` are deliberately `warn`-severity
  - `constitution` stays `fail`-severity
- Vue typecheck clean
- Full Python suite: 3778/3778 passing
- Preflight: `all_passed: True`

## [2.86.0] - 2026-05-25

### Added (Agents activity feed + dispatch copy — PR69)

- **`GET /api/agents/activity?period=today|week|month|all`** —
  per-department call counts derived from PR47 telemetry rows whose
  `category` starts with `subagent:`. Per-agent attribution will
  land when orchestrators set
  `ARKA_CALL_CATEGORY=subagent:<dept>:<agent>`.
- **Activity (7d) column** on the Agents list — green dot + call
  count when the agent's department has been invoked in the last 7
  days, em-dash when quiet.
- **▶ Copy mention** button per agent row — copies a ready-to-paste
  string like `Use Paulo (Tech Lead, dept dev, tier 1) for this
  task.` so the operator can drop it into the next prompt. Icon
  flips to a check for 1.5s on success.
- **Resilient telemetry handling** — invalid period falls back to
  `week`, non-subagent categories are filtered out, partial-cost
  rows still aggregate the known totals.

### Test coverage

- 8 new `tests/python/test_agents_activity_api.py` cases:
  - Empty telemetry, grouping by dept, non-subagent filtering,
    `subagent:` (no dept) bucketing under `unknown`, invalid period
    fallback, null-cost preservation, partial-cost aggregation,
    token aggregation.
- Vue typecheck clean on the agents list page
- Full Python suite: 3769/3769 passing
- Preflight: `all_passed: True`

## [2.85.0] - 2026-05-25

### Added (Commands page: ▶ Copy + ★ Favorites — PR68)

- **Per-row Copy button** — one click puts the command on the
  clipboard. Icon flips to a check for 1.5s on success; toast
  confirms. Closes Daniel Ek's audit question ("what's the
  job-to-be-done here vs the CLI?" → fast lookup → paste back).
- **★ Favorites** — operators star commands with a ghost icon; the
  list is persisted in `localStorage` under `arkaos_command_favorites`.
  Favourites pin to the top of the "All" view; a second tab
  "Favorites" shows just the starred ones. Header badge shows the
  count.
- **Header shows total + favorites count** so the operator sees the
  scale of the catalogue.
- **Click on the command code itself** still expands the keywords
  pane; the ★ + ▶ buttons stop event propagation so a star/copy
  doesn't toggle the expansion.

### Test coverage

- Vue typecheck clean
- Full Python suite: 3761/3761 passing (no backend changes)
- Preflight: `all_passed: True` (after the earlier PR67 CHANGELOG
  sanitisation referenced below)

## [2.84.0] - 2026-05-25

### Changed (Tasks page → real-time jobs view — PR67)

- **`dashboard/app/pages/tasks.vue` rewritten** against `/api/jobs`
  (the SQLite job queue) instead of the legacy `/api/tasks`
  endpoint. Jobs are what knowledge ingest, persona-builder bulk
  fetches, and future workflow primitives all flow through.
- **Live updates** via `/ws/tasks` WebSocket — every
  `job_progress` / `job_complete` / `job_failed` / `job_cancelled`
  broadcast updates the matching row in place. Header shows a
  `Live` / `Offline` badge so the operator sees the connection
  state at a glance.
- **Per-row Cancel** button on `queued` and `processing` jobs.
  Calls `DELETE /api/jobs/{id}` (existing); WS broadcast flips
  the row to `cancelled`; success toast on confirmation.
- **Empty state fixed** — the previous hint pointed at a dead
  command (`npx arkaos index`). Now it directs the operator to
  the Knowledge tab with a CTA button.
- **Five summary cards** (Total / Active / Queued / Completed /
  Failed) instead of four, because Failed deserves its own count.
- **Inline error display** — failed jobs show the error message
  truncated in the source cell so the operator doesn't have to
  drill down to see what broke.

### Fixed (PR66 client-name leak)

- Sanitised `tests/python/test_command_center_api.py` fixtures.
  A confidential client identifier had leaked into the test data;
  replaced with neutral placeholders. The leak was caught by
  `core/release/preflight::check_no_client_name_leaks` before
  publish. Per `[[feedback_npm_publish_safety]]`,
  `[[feedback_confidentiality]]` — client names never reach the repo.

### Test coverage

- 15 existing `test_command_center_api.py` cases still pass with
  the sanitised fixtures
- Vue typecheck clean on the rewritten `tasks.vue`
- Full Python suite: 3761/3761 passing
- Preflight: `all_passed: True`

## [2.83.0] - 2026-05-25

### Added (Index → Command Center — PR66)

- **`GET /api/overview/command-center`** — telemetry-driven aggregate:
  - `greeting` (name, role, company, language from `~/.arkaos/profile.json`)
  - `today_cost` (total USD, calls, tokens in/out, cache hit rate from PR47)
  - `projects` (parsed from `~/.arkaos/projects/<slug>.md` descriptors;
    enriched with last-commit-days via `git log -1 --format=%ct`)
  - `recent_incidents` (last 8 bypass / blocked rows from
    `~/.arkaos/telemetry/enforcement.jsonl`)
  - `quick_actions` (curated command suggestions with one-click copy)
- **`dashboard/app/pages/index.vue` rebuilt** from a 6-stat-card
  overview that re-counted things you already knew (agents=62,
  skills=256) into a real operator command center:
  - **Hero** — personalised greeting + today's cost/calls/cache
  - **Projects column (2/3 width)** — each project with stack badges,
    status pill, ecosystem tag, last-commit timestamp (green/yellow/red
    by freshness)
  - **Incidents column (1/3 width)** — recent bypass / blocked events
    with tool + reason
  - **Quick actions** — click-to-copy `/arka update`, `/arka costs`,
    `/arka conclave`, `/dev review`
- Profile manager (`core/profile/manager.py`) now resolves the default
  path at call time so HOME changes (tests, multi-tenant daemons) are
  honoured. Production behaviour unchanged.

### Why

Per the dashboard audit ("Stats são números cegos — não dão
indicação de saúde"), the homepage was a vanity board. The user
asked: "what justifies this page existing if the CLI shows the same
counts?" PR66 answers: nothing — replace it with what the operator
actually needs at session start.

### Test coverage

- 15 new `tests/python/test_command_center_api.py` cases:
  - `_parse_descriptor` (minimal, full frontmatter, stack-cap-6,
    scalar stack, malformed YAML)
  - `_last_commit_days` (missing path, not-a-repo, empty string)
  - `_recent_incidents` (missing log, filter bypass/blocked,
    cap-at-limit, skip malformed)
  - `/api/overview/command-center` (required-keys shape,
    greeting-from-profile, empty-projects)
- 1 updated profile-manager behaviour (call-time path resolution)
- Vue typecheck clean
- Full Python suite: 3761/3761 passing

## [2.82.0] - 2026-05-25

### Added (Budget rebuild — PR65)

- **`GET /api/llm-costs?period=today|week|month|all`** — exposes the
  full PR47 `CostSummary`: per-provider, per-model, **per-category**,
  top sessions, advisories, corrupt-line count.
- **`GET /api/llm-costs/trend?days=N`** — daily rollup with one bucket
  per day in the window (zeros included so the chart never has gaps).
  Floored at 1, capped at 90, malformed timestamps skipped, missing
  costs surface as `null` instead of zero.
- **`dashboard/app/pages/budget.vue`** rebuilt against the new
  endpoints. Replaces the tokens-only view that
  `[[feedback_budget_ux]]` complained about:
  - Top-line: total cost USD + call count + tokens in/out + cache hit %
  - 7-day inline trend chart (tooltip per bar: date, cost, calls)
  - Breakdown tabs: **By category** / **By provider** / **By model**
  - Top sessions list with cost per session
  - Advisory banner when sessions exceed the $5 threshold
  - Period selector (Today / 7 days / 30 days / All time)
- **By Category** view explicitly explains the empty state — operators
  who haven't set `ARKA_CALL_CATEGORY` (PR60) see a hint instead of
  a blank chart.

### Why

`[[feedback_budget_ux]]` flagged the legacy page as confusing:
"tokens shown as $, tiers meaningless, needs department-based
redesign". PR47 added the data layer (category-aware telemetry);
PR60 wired the env-var auto-populator; PR65 finally shows it. The
3-PR chain closes the loop: real cost USD attributable by category.

### Test coverage

- 11 new `tests/python/test_llm_costs_api.py` cases:
  - `/api/llm-costs` — invalid-period rejection, PR47 shape contract,
    all valid periods round-trip
  - `/api/llm-costs/trend` — one bucket per day, days clamp (1, 90),
    aggregation correctness, null-cost preservation, quiet-day zeros,
    malformed-ts skip, out-of-window skip
- Vue typecheck clean
- Full Python suite: 3746/3746 passing
- Preflight: `all_passed: True`

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
