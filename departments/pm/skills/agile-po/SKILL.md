---
name: pm/agile-po
description: >
  Agile product ownership: user story writing, acceptance criteria,
  sprint planning, epic breakdown, backlog prioritization, velocity tracking.
  INVEST-compliant stories with Given-When-Then acceptance criteria.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Agile Product Owner — `/pm agile-po <action>`

> **Agent:** Carolina (PM Lead) | **Frameworks:** Scrum, Shape Up, Continuous Discovery

## Actions

| Action | What It Does |
|--------|-------------|
| `story <requirement>` | Write INVEST-compliant user story with acceptance criteria |
| `epic <name>` | Break epic into sprint-sized stories with dependencies |
| `sprint <velocity>` | Plan sprint: capacity, committed items, stretch goals |
| `prioritize` | Score and rank backlog using value/effort matrix |

## User Story Template

```
As a [persona],
I want to [action/capability],
So that [benefit/value].
```

### Story Types

| Type | Template | Example |
|------|----------|---------|
| Feature | As a [persona], I want to [action] so that [benefit] | As a user, I want to filter results so I find items faster |
| Improvement | As a [persona], I need [capability] to [goal] | As a user, I need faster loads to complete tasks without frustration |
| Bug Fix | As a [persona], I expect [behavior] when [condition] | As a user, I expect my cart to persist when I refresh |
| Enabler | As a developer, I need to [task] to enable [capability] | As a developer, I need caching to enable instant search |

## Acceptance Criteria — `Given [precondition], When [action], Then [outcome]`

| Story Points | Min AC | Categories to Cover |
|-------------|--------|---------------------|
| 1-2 | 3-4 | Happy path, validation, error handling |
| 3-5 | 4-6 | + performance, accessibility |
| 8 | 5-8 | + edge cases, security |
| 13+ | Split the story | -- |

## INVEST Validation

| Criterion | Pass If... |
|-----------|-----------|
| **I**ndependent | No blocking dependencies on uncommitted stories |
| **N**egotiable | Multiple implementation approaches possible |
| **V**aluable | Clear benefit in "so that" clause |
| **E**stimable | Team can size it (understood well enough) |
| **S**mall | Fits in one sprint (8 points max) |
| **T**estable | Clear acceptance criteria exist |

## Epic Breakdown

| Splitting Technique | When to Use |
|--------------------|-------------|
| By workflow step | Linear process (checkout > cart + payment + confirm) |
| By persona | Multiple user types (admin dashboard + user dashboard) |
| By data type | Multiple inputs (import CSV + import Excel) |
| By operation | CRUD (create + edit + delete) |
| Happy path first | Risk reduction (basic flow + error handling + edge cases) |

## Sprint Planning

`Capacity = Avg Velocity x Availability` | Committed: 80-85% | Stretch: 10-15%

| Availability | Factor | Prioritization | Weight |
|-------------|--------|----------------|--------|
| Full sprint | 1.0 | Business Value | 40% |
| One member 50% out | 0.9 | User Impact | 30% |
| Holiday in sprint | 0.8 | Risk / Dependencies | 15% |
| Multiple out | 0.7 | Effort | 15% |

## Sprint Metrics

| Metric | Target | Definition of Done |
|--------|--------|--------------------|
| Velocity | Stable within 10% | Code reviewed |
| Commitment Reliability | > 85% | Tests passing |
| Scope Change | < 10% | AC verified |
| Carryover | < 15% | Deployed to staging, PO accepted |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Story without acceptance criteria → flag untestable work
- Sprint with >80% capacity planned → flag burnout/scope creep risk
- Epic without success metric → flag unmeasurable outcome

## Output

```markdown
## [Action] — [Context]

### User Story: [ID]
**Type:** [feature/improvement/bug/enabler] | **Points:** [N] | **Priority:** [H/M/L]

As a [persona], I want to [action], so that [benefit].

### Acceptance Criteria
1. Given [X], When [Y], Then [Z]
2. ...

### INVEST Checklist
[validated items]

### Sprint Loading (if sprint action)
Capacity: [N] pts | Committed: [N] pts | Stretch: [N] pts
[prioritized story list]
```
