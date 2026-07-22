---
name: arka-dev-spec
description: >
  Spec-driven development gate, constitution MUST rule spec-driven
  (Constitution #7 — no code without an approved spec): creates, validates,
  and manages feature specifications with the Living Specs engine
  (core/specs/) — scope, acceptance criteria, data model, API contracts,
  edge cases, test scenarios. TRIGGER: "spec", "requirements", "requisitos",
  "write spec", "escreve a spec", "critérios de aceitação", "/dev spec";
  auto-invoked as Phase 0 of every code-modifying dev workflow — load BEFORE
  writing any code. SKIP: multi-agent planning or "how do we execute this"
  -> /arka-forge (the Forge plans the WORK; spec defines the WHAT);
  reviewing existing code -> dev/code-review; /dev debug and /dev refactor
  operate on existing code and need no new spec.
---

# Spec-Driven Development — ARKA OS Dev Department

No code is written until a detailed spec exists and is approved. **Constitution MUST rule spec-driven (#7).**

## Commands

| Command | Description |
|---------|-------------|
| `/dev spec <description>` | Create a feature spec interactively |
| `/dev spec validate` | Validate an existing spec for completeness |
| `/dev spec list` | List all specs in the current project |

## Auto-Invocation (Phase 0)

Automatically invoked before `/dev feature`, `/dev api`, `/dev db`, and code-modifying `/dev do`. Skip for `/dev debug` and `/dev refactor` (operate on existing code).

Paulo checks for an approved spec. If none exists, triggers the interactive creation workflow.

## Workflow: /dev spec (6 Steps)

### Step 1: Context Loading
Paulo reads: PROJECT.md, CLAUDE.md, recent git log. Checks Obsidian `Projects/<name>/Specs/` for related specs.

### Step 2: Requirements Gathering
Ask only genuinely unclear questions. Core: problem, actors, inputs/outputs, constraints, done criteria. Follow-up: backend/frontend, existing patterns, scale, third-party APIs. Batch 2-3 questions.

### Step 3: Spec Drafting
Full template (see below). Omit genuinely irrelevant sections.

### Step 4: User Approval
Present full spec via `AskUserQuestion`. Iterate until user approves.

### Step 4a: Visual Spec Companion (optional)
After approval, when the spec is flow-heavy (multi-actor flows, API
call chains, pipelines, state machines, several system touchpoints),
offer a diagram via `dev/diagram` so the user SEES the feature before it
is built. Pick the type from the spec's dominant shape: API Contracts →
`sequence` · data pipelines/lineage → `dataflow` · feature flow with
actors → `workflow` · system touchpoints → `architecture` · state
machines → `lifecycle` (static ERDs stay with dev/db-schema). Author the IR from the approved sections only —
the diagram illustrates the spec, it never introduces scope. Deliver,
open for the user, and record the receipt for Step 5. Skip silently for
CRUD-simple specs; if Node is unavailable, say the companion is
unavailable and continue — the spec itself is never blocked.

### Step 5: Save to Obsidian
Path: `Projects/<name>/Specs/SPEC-<slug>.md`. Update `status: approved`. Link from project Home.md.
When Step 4a produced a diagram: save the IR JSON to
`Projects/<name>/Specs/visuals/SPEC-<slug>.<type>.json` and record it in
the spec frontmatter `visuals:` list as `{type, ir, html, sha256}` (the
IR is the regenerable source of truth; copy the HTML into the vault only
on request).

### Step 6: Return to Calling Workflow
Phase 2 uses spec for research. Phase 3 uses it as design source of truth. Phase 4 uses acceptance criteria. Phase 7 uses test scenarios.

## Spec Template

```markdown
---
type: spec
status: draft
feature: <slug>
project: <name>
date_created: <YYYY-MM-DD>
tags: [spec, <project-tag>, <feature-tag>]
visuals: []  # optional — {type, ir, html, sha256} entries from Step 4a
---

# SPEC: <Feature Title>

## Overview
**Problem:** ... **Goal:** ... **Actors:** ...

## Scope
**In scope:** ... **Out of scope:** ...

## Acceptance Criteria
1. Given [context], when [action], then [result]
2. ...

## Data Model
| Entity | Fields | Relationships |
|--------|--------|---------------|
| ... | ... | ... |
**Migrations:** [ ] Create/alter table X | [ ] Index on Y

## API Contracts
### POST /api/v1/resource
**Request:** `{ "field": "value" }`
**Response (201):** `{ "id": 1, "field": "value" }`
**Errors:** 400, 401, 409

## UI/UX Requirements
**Screen:** [Name] — [Description]
**States:** loading, empty, error, success
**Components:** [list]

## Edge Cases
1. What happens when [edge case]?
2. ...

## Test Scenarios
| # | Scenario | Type | Expected |
|---|----------|------|----------|
| 1 | ... | Feature/Unit | ... |

## Dependencies
- [ ] [dependency]
```

## Workflow: /dev spec validate

Check: Overview · Scope in/out · ≥3 testable AC · Data Model (if data changes) · API Contracts (if API changes) · ≥2 Edge Cases · Test scenarios matching AC.

## Workflow: /dev spec list

Search `Projects/<name>/Specs/SPEC-*.md`. Display: Feature, Status, Date, AC count. Inform if none found.

## Key Principles + Obsidian

Specs: living documents (acknowledge changes) · Spec = contract · 30 min saves rework · Build with user · Adapt template to feature type. Obsidian: `Projects/<name>/Specs/SPEC-<slug>.md`