# Severity Playbook — Deep Reference

> SEV1-4 definitions, escalation paths, communication templates, PIR framework, and anti-patterns.

## Severity Definitions with Examples

| Level | Definition | User Impact | Examples |
|-------|-----------|-------------|---------|
| **SEV1** | Complete service outage, data loss, active security breach | 100% of users or data integrity compromised | Database corruption, payment system down, credentials leaked, entire site 500 |
| **SEV2** | Major feature degraded, >25% users affected | Significant functionality lost | Search broken, checkout intermittent, API latency >10x, auth failures for subset |
| **SEV3** | Single feature broken, workaround exists | Minor inconvenience, <10% users | Export fails (manual workaround), slow dashboard, broken notification emails |
| **SEV4** | Cosmetic, dev/staging only, no user impact | None or negligible | UI alignment bug, staging env down, deprecation warning, flaky test |

## Escalation Paths

### SEV1 — Full Escalation

```
T+0min    Alert fires or report received
T+5min    On-call engineer acknowledges, starts investigation
T+10min   Incident Commander assigned, war room opened
T+15min   First stakeholder notification sent
T+15min   Engineering lead and CTO notified
T+30min   If no mitigation path: escalate to vendor/cloud provider
T+60min   If unresolved: executive briefing, consider public status page
T+4h      If unresolved: assemble cross-team tiger team
```

### SEV2 — Team Escalation

```
T+0min    Alert fires or report received
T+15min   On-call engineer acknowledges
T+30min   Team lead notified, incident channel created
T+1h      First stakeholder update
T+2h      If unresolved: escalate to engineering manager
T+4h      If unresolved: consider SEV1 upgrade
```

### SEV3 — Standard Response

```
T+0min    Ticket created automatically or manually
T+2h      Engineer assigned during business hours
T+1d      Initial investigation and fix ETA
T+3d      Fix deployed or workaround documented
```

### SEV4 — Backlog

```
T+0min    Ticket created, tagged low priority
Next sprint  Triaged and prioritized
```

## Severity Upgrade/Downgrade Criteria

| Trigger | Action |
|---------|--------|
| Impact expands beyond initial scope | Upgrade severity |
| Duration exceeds 2x expected MTTR | Upgrade severity |
| Data integrity concerns emerge | Upgrade to SEV1 |
| Workaround found and confirmed | Consider downgrade |
| Impact narrower than initial assessment | Downgrade severity |

## Communication Templates

### Initial Notification (SEV1/SEV2)

```
INCIDENT: [SEV{N}] {Service Name} - {Brief Description}

Impact: {What users experience, how many affected}
Start time: {ISO 8601 timestamp, timezone}
Status: INVESTIGATING

Incident Commander: {Name}
Technical Lead: {Name}
War Room: {Slack channel / Zoom link}

Next update: {Time, max 15min for SEV1, 30min for SEV2}
```

### Status Update

```
INCIDENT UPDATE #{N}: [SEV{level}] {Service Name}

Status: INVESTIGATING | IDENTIFIED | MITIGATING | MONITORING | RESOLVED
Duration: {elapsed time}

What we know:
- {Finding 1}
- {Finding 2}

Actions taken:
- {Action 1}
- {Action 2}

Next steps:
- {Planned action with owner}

ETA to resolution: {estimate or "Under investigation"}
Next update: {time}
```

### Resolution Notification

```
RESOLVED: [SEV{level}] {Service Name} - {Brief Description}

Duration: {start} to {end} ({total})
Root cause: {1-2 sentence summary}
Fix applied: {what was done}
Users affected: {count or percentage}

Post-Incident Review scheduled: {date/time}
Action items will be tracked in: {ticket link}
```

### Customer-Facing Status Page

```
[Investigating] We are aware of issues with {feature}. Our team is actively
investigating. We will provide an update within {timeframe}.

[Identified] We have identified the cause of {issue}. A fix is being implemented.
Expected resolution: {ETA}.

[Resolved] The issue with {feature} has been resolved. All systems are operating
normally. We apologize for the inconvenience.
```

## Post-Incident Review (PIR) Template

### Header

| Field | Value |
|-------|-------|
| Incident ID | INC-YYYY-NNN |
| Severity | SEV{N} |
| Date | YYYY-MM-DD |
| Duration | {start} to {end} ({total}) |
| Incident Commander | {Name} |
| Technical Lead | {Name} |
| PIR Author | {Name} |
| PIR Date | {date, within 48h of resolution} |

### Timeline (Required for SEV1/SEV2)

| Time (UTC) | Event | Source |
|------------|-------|--------|
| HH:MM | Alert fired: {description} | Monitoring |
| HH:MM | On-call acknowledged | PagerDuty |
| HH:MM | IC assigned, war room opened | Manual |
| HH:MM | Root cause identified: {description} | Investigation |
| HH:MM | Mitigation applied: {action} | Deployment |
| HH:MM | Service confirmed restored | Monitoring |

### Root Cause Analysis

**5 Whys format:**

```
1. Why did the service go down?
   -> Database connection pool exhausted
2. Why was the pool exhausted?
   -> Slow query holding connections for 30s+
3. Why was the query slow?
   -> Missing index on users.email after migration
4. Why was the index missing?
   -> Migration script did not include index creation
5. Why was the missing index not caught?
   -> No performance test in CI for migration scripts
```

### Action Items Table

| # | Action | Type | Owner | Due Date | Priority | Status |
|---|--------|------|-------|----------|----------|--------|
| 1 | Add index on users.email | Fix | {name} | {date} | P0 | Done |
| 2 | Add migration perf tests to CI | Prevent | {name} | {date} | P1 | Open |
| 3 | Add connection pool alert at 80% | Detect | {name} | {date} | P1 | Open |
| 4 | Document DB migration checklist | Process | {name} | {date} | P2 | Open |

Action item types: **Fix** (address this incident), **Prevent** (stop recurrence), **Detect** (catch it earlier), **Process** (improve response).

## PIR Quality Checklist

- [ ] Timeline is complete with timestamps from monitoring (not memory)
- [ ] Root cause goes deep enough (5 Whys or equivalent)
- [ ] Action items have owners and due dates (no orphaned items)
- [ ] Action items include detection improvements, not just fixes
- [ ] Blameless language throughout (systems, not people)
- [ ] Shared with broader engineering team
- [ ] Runbooks updated with new knowledge
- [ ] Follow-up review scheduled for action item completion

## Anti-Patterns

| Anti-Pattern | Why It Hurts | Fix |
|-------------|-------------|-----|
| Skipping severity classification | Wrong response level, wasted effort or delayed response | Classify within first 5 minutes, always |
| Hero culture (one person does everything) | Burnout, no knowledge sharing, SPOF | Separate IC and Tech Lead roles |
| No communication cadence | Stakeholders assume the worst, escalate unnecessarily | Set timer for updates, even if "still investigating" |
| Blame-focused PIR | People hide mistakes, no systemic improvement | Blameless by policy, focus on systems |
| PIR action items with no owners | Nothing gets done, same incident recurs | Every action item requires name + date |
| Never upgrading severity | SEV3 that is actually SEV1 gets slow response | Review upgrade criteria at every status update |
| Fix-only action items | Catches this incident but not the next variant | Always include Detect and Prevent items |
| PIR delayed beyond 1 week | Details forgotten, momentum lost | Schedule within 48 hours, hard deadline 5 days |

## Metrics to Track

| Metric | Target | Measures |
|--------|--------|----------|
| MTTD (Mean Time to Detect) | < 5 min | Monitoring effectiveness |
| MTTA (Mean Time to Acknowledge) | < 10 min (SEV1) | On-call responsiveness |
| MTTR (Mean Time to Resolve) | < 1h (SEV1), < 4h (SEV2) | Resolution efficiency |
| PIR completion rate | 100% for SEV1/SEV2 | Learning culture |
| Action item completion rate | > 90% within due date | Follow-through |
| Recurrence rate | < 5% same root cause | Prevention effectiveness |
