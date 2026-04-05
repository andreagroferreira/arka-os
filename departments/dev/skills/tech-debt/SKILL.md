---
name: dev/tech-debt
description: >
  Identify, classify, score, and prioritize technical debt. Generate remediation plans with cost-of-delay analysis.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Tech Debt Tracker — `/dev tech-debt`

> **Agent:** Andre (Senior Backend Dev) | **Framework:** Ward Cunningham Debt Metaphor, Cost-of-Delay

## Debt Classification

| Category | Examples | Detection Method |
|----------|---------|-----------------|
| **Code Debt** | Duplicated code, long methods, deep nesting, god classes | Static analysis, code review |
| **Architecture Debt** | Tight coupling, missing abstraction layers, monolith bloat | Dependency analysis, module boundaries |
| **Test Debt** | Low coverage, flaky tests, missing integration tests | Coverage reports, CI failure rates |
| **Dependency Debt** | Outdated packages, deprecated APIs, unsupported frameworks | `npm audit`, `composer audit`, version checks |
| **Documentation Debt** | Missing API docs, stale README, undocumented decisions | File age analysis, ADR gaps |
| **Infrastructure Debt** | Manual deployments, missing IaC, no monitoring | Pipeline audit, runbook gaps |

## Scanning Checklist

- [ ] Run static analysis (PHPStan, ESLint, Pylint)
- [ ] Check test coverage (`--coverage` reports)
- [ ] Audit dependencies for CVEs and outdated versions
- [ ] Identify files with highest churn (git log frequency)
- [ ] Find largest files and longest methods
- [ ] Check for TODO/FIXME/HACK comments
- [ ] Review CI pipeline failure rate (flaky tests)
- [ ] Assess documentation freshness

## Severity Scoring (1-10)

| Factor | Weight | How to Score |
|--------|--------|-------------|
| **Impact** | 3x | How much does it slow development? (1=minor, 10=blocking) |
| **Risk** | 2x | Likelihood of production incident? (1=unlikely, 10=imminent) |
| **Spread** | 1x | How many areas affected? (1=isolated, 10=pervasive) |
| **Fix Cost** | 1x | Effort to remediate (1=hours, 10=months) -- lower is worse |

**Debt Score = (Impact x 3) + (Risk x 2) + (Spread x 1) + ((10 - Fix Cost) x 1)**

Score ranges: **50-70** Critical | **35-49** High | **20-34** Medium | **< 20** Low

## Prioritization Matrix

| | Low Fix Cost | High Fix Cost |
|--|-------------|---------------|
| **High Impact** | Fix immediately (quick wins) | Plan dedicated sprint |
| **Low Impact** | Fix opportunistically | Accept or defer |

**Cost-of-Delay rule:** Prioritize debt that compounds -- items where delay increases future fix cost (e.g., deprecated framework versions, growing coupling).

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Analysis paralysis | Time-box scanning to 2 hours max |
| Trying to fix everything | Focus on top 5 by score |
| Ignoring business context | Tie every item to velocity or risk |
| No tracking | Add debt items to backlog with labels |
| Inconsistent scoring | Use the scoring table above consistently |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- TODO count >50 in codebase → flag tech debt accumulation
- Dependencies >2 major versions behind → flag upgrade urgency
- No tech debt review cadence → flag growing hidden cost

## Output

```markdown
## Tech Debt Report: <project>

### Summary
- Total items: {count}
- Critical: {count} | High: {count} | Medium: {count} | Low: {count}
- Estimated total remediation: {hours/days}

### Top 5 Debt Items (by score)
| # | Category | Description | Score | Fix Cost | Recommendation |
|---|----------|-------------|-------|----------|----------------|

### Quick Wins (high impact, low cost)
1. [Item + action]
2. [Item + action]

### Debt Trends
- New debt this sprint: {count}
- Resolved this sprint: {count}
- Net change: {+/-}

### Recommended Sprint Allocation
- Feature work: 80% | Debt reduction: 20%
- Focus area: [highest-scoring category]
```
