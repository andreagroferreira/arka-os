# ArkaOS Orchestration Protocol

How to coordinate agents across departments for complex, multi-domain work.

## Core Concept

ArkaOS has three layers of execution:

| Layer | What | ArkaOS Equivalent |
|-------|------|-------------------|
| **Agent** | Who is thinking (identity, judgment) | 62 agents with behavioral DNA |
| **Skill** | How to execute (steps, templates) | 250+ department skills |
| **Workflow** | What phases to follow | 24 YAML workflows |

Orchestration connects them for work that crosses department boundaries.

## Four Patterns

### 1. Solo Sprint
One department lead drives a multi-phase sprint.

```
Lead: Ines (Landing)
Phase 1: /landing copy-framework + /landing funnel-design
Phase 2: /landing page-build + /landing seo-optimize
Phase 3: Quality Gate → Ship
```

**Use when:** Single domain, time-constrained, clear scope.

### 2. Domain Deep-Dive
One agent, multiple stacked skills for thorough analysis.

```
Agent: Bruno (Security Engineer)
Stack: /dev security-audit → /dev dependency-audit → /dev red-team → /dev ai-security
Output: Consolidated security report
```

**Use when:** Deep expertise needed, audit/review, compliance assessment.

### 3. Multi-Agent Handoff
Work flows between departments with structured context passing.

```
Phase 1: Tomas (Strategy) → BMC + Five Forces → Handoff
Phase 2: Paulo (Dev) → Spec + Feature → Handoff
Phase 3: Luna (Marketing) → Growth Plan + Email → Handoff
Phase 4: Quality Gate → Launch
```

**Use when:** Cross-department project, sequential expertise needed.

### 4. Skill Chain
Pure procedural execution, no specific agent identity.

```
/content hook-write → headline_scorer.py → /content viral-design → /mkt social-strategy
```

**Use when:** Automated pipeline, well-defined inputs/outputs, no judgment needed.

## Phase Handoff Template

Between phases, pass structured context:

```
Phase [N] complete.
Decisions: [list of decisions made]
Artifacts: [list of files/documents created]
Open questions: [what the next phase needs to resolve]
Next: [department]/[agent] + [skills]
```

## Pattern Selection

| Departments | Needs Judgment? | Sequential? | Pattern |
|------------|----------------|-------------|---------|
| 1 | Yes | — | Solo Sprint |
| 1 | No | — | Skill Chain |
| 1 | Deep analysis | — | Domain Deep-Dive |
| 2+ | Yes | Yes | Multi-Agent Handoff |
| 2+ | No | Yes | Skill Chain |

## Rules

1. **One agent at a time** — don't blend two agents in the same execution
2. **Skills stack freely** — load as many as the task needs
3. **Context carries forward** — always pass handoff between phases
4. **Quality Gate is mandatory** — no pattern skips the final review
5. **User decides** — orchestration is a recommendation, user can override
