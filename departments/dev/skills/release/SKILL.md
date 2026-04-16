---
name: dev/release
description: >
  Release planning and execution: versioning strategy, readiness checklists, deployment coordination, rollback procedures, and hotfix management.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Release Management — `/dev release`

> **Agent:** Paulo (Dev Lead) | **Framework:** SemVer, DORA Metrics, Continuous Delivery

## Versioning Strategy (SemVer)

| Bump | When | Example |
|------|------|---------|
| **MAJOR** | Breaking changes, removed APIs | 1.x.x -> 2.0.0 |
| **MINOR** | New features, backward compatible | 1.2.x -> 1.3.0 |
| **PATCH** | Bug fixes, security patches | 1.2.3 -> 1.2.4 |
| **Pre-release** | Alpha/beta/RC testing | 1.3.0-beta.1 |

**Auto-detection from conventional commits:**
- `feat!:` or `BREAKING CHANGE:` footer -> MAJOR
- `feat:` -> MINOR
- `fix:`, `perf:`, `security:` -> PATCH
- `docs:`, `test:`, `chore:` -> No bump

## Release Readiness Checklist

### Code Quality
- [ ] All CI checks passing (lint, type-check, build)
- [ ] Test coverage >= 80%
- [ ] No critical/high static analysis findings
- [ ] Security audit clean (`/dev security-audit`)
- [ ] Dependency audit clean (`/dev dependency-audit`)

### Documentation
- [ ] CHANGELOG.md updated (`/dev changelog`)
- [ ] Migration guide written for breaking changes
- [ ] API documentation reflects changes
- [ ] Deployment notes prepared

### Approvals
- [ ] Code review approved
- [ ] QA validation complete (Marta -- Quality Gate)
- [ ] Product sign-off on feature scope
- [ ] Security clearance (if applicable)

## Deployment Sequence

| Phase | Timing | Action |
|-------|--------|--------|
| **Code Freeze** | T-24h | No new merges, final validation |
| **Migrations** | T-2h | Run and validate DB schema changes |
| **Deploy** | T-0 | Blue-green or canary rollout |
| **Verify** | T+1h | Monitor error rates, latency, golden signals |
| **Rollback Window** | T+4h | Go/no-go decision on keeping release |

## Rollback Triggers

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Error rate spike | > 2x baseline for 15 min | Auto-rollback or IC decision |
| Latency degradation | p99 > 2x baseline for 10 min | Investigate, rollback if no fix |
| Core feature failure | Any critical path broken | Immediate rollback |
| Data corruption | Any evidence | Immediate rollback + incident |

## Rollback Types

| Type | Method | Notes |
|------|--------|-------|
| **Code** | Revert to previous container/build | Fastest, prefer this |
| **Feature flag** | Disable flag for new code path | No deploy needed |
| **Database** | Forward-only migration preferred | Never drop columns in rollback |
| **Infrastructure** | Blue-green switch | DNS propagation delay |

## Hotfix Procedure

| Severity | SLA | Process |
|----------|-----|---------|
| **P0** Critical | 2 hours | Emergency branch from last tag, minimal fix, expedited deploy |
| **P1** High | 24 hours | Expedited review, deploy in next window |
| **P2** Medium | Next release | Normal PR process |

**Hotfix steps:**
1. Branch from last stable tag: `git checkout -b hotfix/description vX.Y.Z`
2. Apply minimal fix (root cause only)
3. Run automated tests
4. Deploy with expedited approval
5. Merge back to main and develop
6. Schedule PIR for P0/P1

## DORA Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|---------------|
| **Lead Time** | < 1 day | Commit to production |
| **Deploy Frequency** | Daily/weekly | Releases per period |
| **Change Failure Rate** | < 15% | Releases causing incidents |
| **MTTR** | < 1 hour | Incident to resolution |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No rollback plan documented → flag deployment risk
- Breaking change without major version bump → flag SemVer violation
- Release without changelog entry → flag documentation gap

## Output

```markdown
## Release Plan: v{X.Y.Z}
### Version Bump: {MAJOR|MINOR|PATCH} | Reason: {summary}
### Readiness: Code quality [PASS/FAIL] | Docs [PASS/FAIL] | Approvals [PASS/FAIL]
### Changes: Features {count} | Fixes {count} | Breaking {count}
### Deployment: {blue-green/canary/rolling} | Rollback: {plan} | Risk: {LOW/MEDIUM/HIGH}
```
