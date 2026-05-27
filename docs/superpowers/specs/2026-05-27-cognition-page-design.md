# Spec — Cognition page (Dreaming + learning monitoring)

- **Date:** 2026-05-27
- **Status:** Approved (design)
- **Feature:** #1 of 3 release features. Independent sub-project.
- **Owner:** dev squad (Paulo)

## Problem

The Cognitive Layer (`core/cognition/`) already runs Dreaming — it surfaces
insights from the operator's vault + session digests and writes them to
`<vault>/Projects/ArkaOS/Dreams/*.md` as `type: arkaos-insight` markdown
(date, title, confidence, sources, tags, body). Today there is **no way to
see these from the dashboard** — the operator can't monitor what the system
is learning. This page surfaces that existing data. No new cognition engine.

## Scope

**In scope**
- A dedicated `/cognition` dashboard page (sidebar entry "Dreaming", brain icon).
- A feed of recent insights: date, confidence badge, tags, sources (as
  wikilinks), expandable markdown body. Filter by time window (1/7/30 days),
  confidence, and tag.
- A status header: insight counts (today / 7d / total), confidence breakdown,
  and an Active/Idle indicator derived from the most recent insight date
  (Active when the last insight is within 3 days).
- Backend endpoints reading existing data via `core.cognition.dreams_reader`.

**Out of scope (YAGNI / follow-up)**
- "Run Dreaming now" / daemon start-stop control AND a live daemon-running
  (scheduler lock file) indicator — both belong with the autostart / scheduler
  work, feature #2. The page uses last-insight recency as a freshness signal
  instead, which is more meaningful (a daemon can be "up" yet produce nothing).
- Research profile + reorganizer detail views (thinner, static data).

## API contract

`GET /api/cognition/insights?days=<int>` (default 7)
→ `{ "insights": [ { date, title, confidence, sources[], tags[], body } ], "available": bool }`
- Resolves `dreams_dir = <profile.vault_path>/Projects/ArkaOS/Dreams` via
  `core.runtime.path_resolver.load_profile()`; calls
  `dreams_reader.list_insights(dreams_dir, days)`.
- `available: false` (empty list) when no vault is configured
  (`ProfileMissingError`) or the dir doesn't exist — never 500.

`GET /api/cognition/status`
→ `{ today, week, total, by_confidence: {high, medium, low}, vault_configured: bool, last_date: str | null }`
- Counts from `list_insights` (days=1, 7, and a large window for "total").
- `last_date` = date of the most recent insight (null when none). Drives the
  Active/Idle pill on the frontend. Never 500.

## Data model

`StoredInsight` (existing, `dreams_reader.py`): `path, date, title,
confidence, sources[], tags[], body`. Serialized to JSON minus `path`.

## Frontend

`dashboard/app/pages/cognition.vue` (layout: default) + sidebar link in
`layouts/default.vue` ("Dreaming", `i-lucide-sparkles`, `/cognition`).
- Header: title + Active/Idle pill (from `last_date` recency) + counts +
  confidence bars.
- Filters: window select (1/7/30d), confidence select, tag filter input.
- Feed: insight cards; confidence badge colour (high=success, medium=warning,
  low=neutral); body rendered with `marked` (existing dep); sources shown as
  chips. Empty state when no insights / no vault.
- Client-only data fetch via `useApi().fetchApi`.

## Edge cases

- No vault configured → page shows a friendly "Connect a vault / Dreaming
  hasn't run yet" empty state, not an error.
- Malformed insight files → skipped by `dreams_reader` already.
- Large bodies → collapsed by default, expandable.

## Tests

- Backend: pytest with a temp dreams_dir of fixture `.md` insights — assert
  `/api/cognition/insights` shape + day filtering, and `/api/cognition/status`
  counts + confidence breakdown + graceful no-vault path. Monkeypatch
  `load_profile` to point at the temp vault.
- Frontend: live browser verification (operator rule) — page renders, feed
  shows, filters work, 0 console errors. Optional Playwright spec as follow-up.

## Quality gate

Marta + Eduardo + Francisca (opus) before ship. Conventional commit, feature
branch, full Python suite green.
