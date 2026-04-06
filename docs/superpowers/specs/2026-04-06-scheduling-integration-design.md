# Design: Scheduling Integration for ArkaOS

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Pattern documented + schedulable workflow examples per department (Approach C)

## Summary

Add scheduling awareness to ArkaOS departments. Unlike Chrome/Computer Use (which add steps to workflows), scheduling is a transversal capability — it defines *how often* a workflow runs, not *what* it does. Each eligible skill gets a `## Scheduling` section with concrete `/loop` and `/schedule` examples.

## Key Insight

Scheduling is NOT a `[SCHEDULED]` step inside a workflow. It's a way to *invoke* the workflow repeatedly. The pattern is:
- Document which workflows are "schedulable" (marked with ⏰)
- Provide ready-to-use `/loop` and `/schedule` examples
- Let the user choose the scheduling method

## Scheduling Methods

| Method | Scope | Persistence | Use Case |
|--------|-------|-------------|----------|
| `/loop <interval> <command>` | Session | Ends when session closes | Active monitoring during work |
| `/schedule` | Cloud/Desktop | Persists across restarts | Overnight/recurring tasks |

## 1. Scheduling Pattern in /arka skill

**File:** `~/.claude/skills/arka/SKILL.md` — new section after Computer Use

Documents the scheduling capability and best practices.

## 2. Schedulable Workflows by Department

### `/dev` (3 skills)
- **code-review** ⏰ — Poll for open PRs
- **security-audit** ⏰ — Weekly dependency audit
- **tdd-cycle** ⏰ — Watch test status

### `/ecom` (2 skills)
- **store-audit** ⏰ — Daily store health check
- **analytics** ⏰ — Hourly conversion monitoring

### `/brand` (1 skill)
- **ux-audit** ⏰ — Weekly lighthouse audit

### `/ops` (2 skills)
- **workflow-automate** ⏰ — Monitor automation health
- **dashboard-build** ⏰ — Check dashboard API health

### `/strat` (2 skills)
- **five-forces** ⏰ — Weekly competitor pricing
- **position** ⏰ — Monthly positioning review

## 3. Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `~/.claude/skills/arka/SKILL.md` | Modify | Add "Scheduling Patterns" section |
| `departments/dev/skills/code-review/SKILL.md` | Modify | Add `## Scheduling` with examples |
| `departments/dev/skills/tdd-cycle/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/dev/skills/security-audit/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/ecom/skills/store-audit/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/ecom/skills/analytics/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/brand/skills/ux-audit/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/ops/skills/workflow-automate/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/ops/skills/dashboard-build/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/strategy/skills/five-forces/SKILL.md` | Modify | Add `## Scheduling` |
| `departments/strategy/skills/position/SKILL.md` | Modify | Add `## Scheduling` |

**Total:** 11 modifications, 0 new files
