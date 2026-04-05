---
name: dev/incident
description: >
  Incident response framework: severity classification, timeline reconstruction, runbook execution, stakeholder communication, and post-incident review.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Incident Response — `/dev incident`

> **Agent:** Paulo (Dev Lead) | **Framework:** Google SRE Incident Management, Blameless PIR

## Severity Classification

| Level | Definition | Response Time | Comms Cadence | Escalation |
|-------|-----------|---------------|---------------|------------|
| **SEV1** | Full outage, data loss, security breach | 5 min | Every 15 min | Immediate exec notification |
| **SEV2** | Partial degradation, >25% users affected | 15 min | Every 30 min | Team lead within 30 min |
| **SEV3** | Single feature affected, workaround exists | 2 hours | Key milestones | Internal team only |
| **SEV4** | Cosmetic, dev/test env, no user impact | Next business day | Standard cycle | Standard ticket |

## Incident Commander Checklist

### Detection (0-5 min)
- [ ] Identify affected services and user impact
- [ ] Classify severity using table above
- [ ] Create incident tracking ticket
- [ ] Establish war room (Slack channel / video bridge)

### Response (5-30 min)
- [ ] Assign Incident Commander (owns process, not debugging)
- [ ] Assign Technical Lead (owns investigation)
- [ ] Check recent deployments and config changes
- [ ] Review error logs and monitoring dashboards
- [ ] Send initial stakeholder notification

### Mitigation
- [ ] Decide: rollback vs. fix-forward
- [ ] Execute mitigation (prefer rollback under pressure)
- [ ] Validate fix with monitoring and end-to-end tests
- [ ] Update status page and stakeholders

### Resolution
- [ ] Confirm service restored to normal
- [ ] Send resolution notification
- [ ] Schedule Post-Incident Review (within 48h)

## Communication Templates

**Initial notification:**
```
[SEV{level}] {Service} -- {Brief Description}
Impact: {what users experience}
Status: Investigating | Mitigating | Resolved
IC: {name} | Tech Lead: {name}
Next update: {time}
```

**Stakeholder update:**
```
[SEV{level}] Update #{n} -- {Service}
Status: {current status}
Actions taken: {what was done}
Next steps: {what happens next}
ETA: {estimate or "investigating"}
```

## Runbook Template

| Section | Content |
|---------|---------|
| **Quick Reference** | Severity indicators, key contacts, critical commands |
| **Detection** | Alert definitions, manual symptom checklist |
| **Initial Response** | Severity assessment, command establishment, first investigation |
| **Mitigation Strategies** | Step-by-step procedures with rollback plans |
| **Recovery** | Service restoration, data consistency checks, notification |
| **Common Pitfalls** | Known failure modes and how to avoid them |

## Post-Incident Review (PIR)

| Framework | When to Use |
|-----------|------------|
| **5 Whys** | Simple, linear root cause chains |
| **Fishbone (Ishikawa)** | Multiple contributing factors |
| **Timeline Analysis** | Complex incidents with many events |

**PIR principles:**
- Blameless -- focus on systems, not people
- Action items have owners and due dates
- Share learnings broadly
- Update runbooks with new knowledge

## Proactive Triggers

Surface these issues WITHOUT being asked:

- SEV1 without defined escalation path → flag response gap
- No PIR template → flag learning gap
- Incident >30min without status update → flag communication failure

## Output

```markdown
## Incident Report: <title>

### Summary
- Severity: SEV{level}
- Duration: {start} to {end} ({total time})
- Impact: {users/services affected}
- Root Cause: {1-2 sentence summary}

### Timeline
| Time | Event |
|------|-------|

### Root Cause Analysis
[5 Whys / Fishbone / Timeline analysis]

### Action Items
| # | Action | Owner | Due | Status |
|---|--------|-------|-----|--------|

### Lessons Learned
1. [Key takeaway]
2. [Key takeaway]
```
