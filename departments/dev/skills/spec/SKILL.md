---
name: arka-dev-spec
description: >
  NON-NEGOTIABLE spec-driven development gate. Creates, validates, and manages feature
  specifications before any code is written. Uses Living Specs engine (core/specs/).
  Interactive workflow that collaborates with the user to produce detailed specs covering
  scope, acceptance criteria, data model, API contracts, UI/UX requirements, edge cases,
  and test scenarios. Auto-invoked as Phase 0 by all code-modifying Tier 1 and Tier 2
  dev workflows (/dev feature, /dev api, /dev db, and code-modifying /dev do).
  This is a Constitution rule (NON-NEGOTIABLE #7) — no code without an approved spec.
  Use when user says "spec", "specification", "requirements", "define feature",
  "write spec", "describe what to build", or when any code-modifying dev command is invoked.
---

# Spec-Driven Development — ARKA OS Dev Department

No code is written until a detailed spec exists and is approved. **NON-NEGOTIABLE #7.**

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

### Step 5: Save to Obsidian
Path: `Projects/<name>/Specs/SPEC-<slug>.md`. Update `status: approved`. Link from project Home.md.

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