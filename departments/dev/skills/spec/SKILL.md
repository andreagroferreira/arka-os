---
name: dev-spec
description: >
  NON-NEGOTIABLE spec-driven development gate. Creates, validates, and manages feature
  specifications before any code is written. Interactive workflow that collaborates with
  the user to produce detailed specs covering scope, acceptance criteria, data model,
  API contracts, UI/UX requirements, edge cases, and test scenarios.
  Auto-invoked as Phase 0 by all code-modifying Tier 1 and Tier 2 dev workflows
  (/dev feature, /dev api, /dev db, and code-modifying /dev do).
  This is a Constitution rule (NON-NEGOTIABLE #7) — no code without an approved spec.
  Use when user says "spec", "specification", "requirements", "define feature",
  "write spec", "describe what to build", or when any code-modifying dev command is invoked.
---

# Spec-Driven Development — ARKA OS Dev Department

No code is written until a detailed spec exists and is approved. This is NON-NEGOTIABLE.

## Commands

| Command | Description | Lead Agent | Tier |
|---------|-------------|------------|------|
| `/dev spec <description>` | Create a feature spec interactively | Paulo | 3 |
| `/dev spec validate` | Validate an existing spec for completeness | Paulo | 3 |
| `/dev spec list` | List all specs in the current project | Paulo | 3 |

## Auto-Invocation (Phase 0)

This skill is automatically invoked as **Phase 0** before any code-modifying workflow:

| Command | Phase 0 Applied |
|---------|----------------|
| `/dev feature` | Yes, always |
| `/dev api` | Yes, always |
| `/dev db` | Yes, always |
| `/dev do` | Yes, when routed to feature/api/db |
| `/dev debug` | No (investigates existing code) |
| `/dev refactor` | No (works on existing code) |

When auto-invoked, Paulo checks if an approved spec already exists. If it does, he loads it as context. If not, he triggers the interactive spec creation workflow below.

## Workflow: /dev spec (Interactive Spec Creation)

### Step 1: Context Loading (Paulo)
- Read project context: PROJECT.md, CLAUDE.md, recent git log
- Identify the project stack, existing patterns, and relevant domain context
- Check Obsidian `Projects/<name>/Specs/` for related or overlapping specs

### Step 2: Requirements Gathering (Paulo)
Use `AskUserQuestion` to understand the feature. Ask only what is genuinely unclear; skip questions the user already answered in their request.

**Core questions (ask as needed):**
- What is the core problem or need this solves?
- Who are the users or actors involved?
- What are the expected inputs and outputs?
- Are there constraints, dependencies, or integrations?
- What does "done" look like? How will we know it works?

**Follow-up questions (if applicable):**
- Does this touch backend, frontend, or both?
- Are there existing patterns in the codebase we should follow?
- Any performance or scale requirements?
- Any third-party services or APIs involved?

Paulo may ask these in batches (2-3 questions at a time) to avoid overwhelming the user. The goal is a complete understanding, not an interrogation.

### Step 3: Spec Drafting (Paulo)
Draft the spec with the following sections. Not every section applies to every feature; omit sections that are genuinely irrelevant.

```markdown
---
type: spec
status: draft
feature: <slug>
project: <project-name>
date_created: <YYYY-MM-DD>
tags:
  - spec
  - <project-tag>
  - <feature-tag>
---

# SPEC: <Feature Title>

## Overview
**Problem:** What problem does this solve?
**Goal:** What is the desired outcome?
**Actors:** Who uses this feature?

## Scope
**In scope:**
- [Specific deliverable 1]
- [Specific deliverable 2]

**Out of scope:**
- [Explicitly excluded item 1]

## Acceptance Criteria
Numbered, testable criteria. Each must be verifiable.

1. Given [context], when [action], then [expected result]
2. Given [context], when [action], then [expected result]
3. ...

## Data Model
Entities, relationships, and schema changes.

| Entity | Fields | Relationships |
|--------|--------|--------------|
| ... | ... | ... |

**Migrations needed:**
- [ ] Create/alter table X
- [ ] Add index on Y

## API Contracts
Endpoints, request/response shapes, status codes.

### POST /api/v1/resource
**Request:**
```json
{ "field": "value" }
```
**Response (201):**
```json
{ "id": 1, "field": "value" }
```
**Errors:** 400 (validation), 401 (unauthorized), 409 (conflict)

## UI/UX Requirements
Screens, components, states, and flows. Skip if backend-only.

- **Screen:** [Name] — [Description]
- **States:** loading, empty, error, success
- **Components:** [Reusable components to create or extend]

## Edge Cases
Boundary conditions, error states, and unusual scenarios.

1. What happens when [edge case]?
2. What if [boundary condition]?
3. How does the system handle [failure scenario]?

## Test Scenarios
Derived from acceptance criteria. Maps to Phase 7 (QA).

| # | Scenario | Type | Expected |
|---|----------|------|----------|
| 1 | ... | Feature/Unit/Component | ... |
| 2 | ... | Feature/Unit/Component | ... |

## Dependencies
External services, existing code, or features that must exist first.

- [ ] [Dependency 1]
- [ ] [Dependency 2]
```

### Step 4: User Approval (Paulo)
Present the complete spec to the user using `AskUserQuestion`:
- Show the full spec content
- Ask: "Does this spec accurately capture what you need? Any changes?"
- Iterate until the user approves

### Step 5: Save to Obsidian (Paulo)
Save the approved spec:
- **Path:** `Projects/<project-name>/Specs/SPEC-<slug>.md`
- **Status:** Update frontmatter `status: approved`
- **Link:** Add wikilink from project Home.md if it exists

### Step 6: Return to Calling Workflow
When invoked as Phase 0, return the spec to the main workflow:
- Phase 2 (Research) uses the spec to focus research
- Phase 3 (Architecture) uses the spec as the design source of truth
- Phase 4 (Implementation) uses acceptance criteria as implementation targets
- Phase 7 (QA) uses test scenarios as the testing plan

## Workflow: /dev spec validate

Validate an existing spec for completeness and consistency:

1. Load the spec from Obsidian or from the user
2. Check completeness:
   - [ ] Has Overview with problem, goal, actors
   - [ ] Has Scope with in/out boundaries
   - [ ] Has at least 3 testable Acceptance Criteria
   - [ ] Has Data Model (if data changes are involved)
   - [ ] Has API Contracts (if API changes are involved)
   - [ ] Has Edge Cases (at least 2)
   - [ ] Has Test Scenarios matching acceptance criteria
3. Check consistency:
   - Data model matches API contracts
   - Test scenarios cover all acceptance criteria
   - Scope matches what acceptance criteria describe
4. Report findings and suggest improvements

## Workflow: /dev spec list

List all specs in the current project:

1. Search Obsidian `Projects/<project-name>/Specs/` for files matching `SPEC-*.md`
2. Display a table: Feature, Status (draft/approved), Date, Acceptance Criteria count
3. If no specs found, inform the user

## Obsidian Output

| Content | Path |
|---------|------|
| Feature specs | `Projects/<name>/Specs/SPEC-<slug>.md` |

## Key Principles

1. **Specs are living documents.** They can be updated as understanding grows, but changes must be acknowledged.
2. **The spec is the contract.** If it is not in the spec, it is not in scope. Scope creep is caught here.
3. **Specs save time.** Thirty minutes of spec writing prevents hours of rework.
4. **User collaboration is key.** The spec is built with the user, not imposed on them.
5. **Not every section is required.** A backend API needs Data Model and API Contracts but not UI/UX. Adapt the template.
