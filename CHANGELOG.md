# Changelog

All notable changes to ArkaOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
