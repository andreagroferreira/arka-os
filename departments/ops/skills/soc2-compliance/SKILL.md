---
name: ops/soc2-compliance
description: >
  SOC 2 readiness assessment, Trust Services Criteria mapping, control matrix generation, evidence collection, and audit preparation.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# SOC 2 Compliance — `/ops soc2-compliance`

> **Agent:** Daniel (Ops Lead) | **Framework:** SOC 2 Type I/II (AICPA), Trust Services Criteria

## Type I vs Type II

| Aspect | Type I | Type II |
|--------|--------|---------|
| Scope | Control design at a point in time | Design AND operating effectiveness over a period |
| Duration | Snapshot (single date) | Observation window (6-12 months) |
| Evidence | Policies, control descriptions | Policies + operating evidence (logs, tickets, configs) |
| Cost | $20K-$50K | $30K-$100K+ |
| Best For | First-time compliance | Mature organizations, enterprise customers |

## Trust Services Criteria

| Category | Criteria | Required | Focus |
|----------|---------|----------|-------|
| Security | CC1-CC9 | Yes (always) | Access, operations, change management, risk |
| Availability | A1 | Optional | Uptime, DR/BCP, capacity planning |
| Confidentiality | C1 | Optional | Data classification, encryption, disposal |
| Processing Integrity | PI1 | Optional | Accuracy, completeness, timeliness |
| Privacy | P1-P8 | Optional | Notice, consent, collection, retention |

## Security Common Criteria (Required)

| Criteria | Domain | Key Controls |
|----------|--------|-------------|
| CC1 | Control Environment | Integrity, oversight, org structure, accountability |
| CC2 | Communication | Internal/external communication, information quality |
| CC3 | Risk Assessment | Risk identification, fraud risk, change analysis |
| CC4 | Monitoring | Ongoing monitoring, deficiency evaluation |
| CC5 | Control Activities | Policies, technology controls |
| CC6 | Logical & Physical Access | Provisioning, authentication, encryption |
| CC7 | System Operations | Vulnerability management, incident response |
| CC8 | Change Management | Authorization, testing, approval |
| CC9 | Risk Mitigation | Vendor and business partner risk |

## Evidence Collection Matrix

| Control Area | Primary Evidence | Secondary Evidence |
|-------------|-----------------|-------------------|
| Access Management | User access reviews, provisioning tickets | Role matrix, access logs |
| Change Management | Change tickets, approval records | Deployment logs, test results |
| Incident Response | Incident tickets, postmortems | Runbooks, escalation records |
| Vulnerability Mgmt | Scan reports, patch records | Remediation timelines |
| Encryption | Config screenshots, certificate inventory | Key rotation logs |
| Backup & Recovery | Backup logs, DR test results | Recovery time measurements |
| Vendor Management | Vendor assessments, SOC reports | Contract reviews, risk registers |

## Audit Readiness Checklist

- [ ] All controls documented with descriptions, owners, and frequencies
- [ ] Evidence collected for entire observation period (Type II)
- [ ] Control matrix reviewed and gaps remediated
- [ ] Policies signed and distributed within last 12 months
- [ ] Access reviews completed at required frequency
- [ ] Vulnerability scans current (no critical/high unpatched beyond SLA)
- [ ] Incident response plan tested within last 12 months
- [ ] Vendor risk assessments current for all subservice organizations
- [ ] DR/BCP tested and documented within last 12 months
- [ ] Employee security training completed for all staff

### Readiness Scoring

| Score | Rating | Action |
|-------|--------|--------|
| 90-100% | Audit Ready | Proceed with confidence |
| 75-89% | Minor Gaps | Address before scheduling audit |
| 50-74% | Significant Gaps | Remediation required |
| < 50% | Not Ready | Major program build-out needed |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No evidence collection process in place for controls -> flag as audit failure risk requiring immediate process setup
- Control gaps identified in Trust Services Criteria coverage -> flag as SOC 2 scope gap needing remediation plan
- Vendor processing customer data without a SOC 2 report or equivalent -> flag as CC9 vendor risk deficiency

## Output

```markdown
## SOC 2 Readiness Assessment: <organization>

### Target: Type <I/II> | Categories: <Security, Availability, ...>

### Readiness Score: X% — <Rating>

### Control Matrix Summary
- Controls mapped: X
- Fully implemented: X | Partial: X | Missing: X

### Evidence Status
- Evidence collected: X/X controls
- Automation coverage: X%

### Gap Analysis
| Priority | Gap | TSC Ref | Remediation | Owner | Target |
|----------|-----|---------|-------------|-------|--------|

### Vendor Assessment Status
- Critical vendors assessed: X/X
- SOC reports on file: X/X

### Recommended Timeline
Gap Assessment -> Remediation -> Type I -> Observation -> Type II
```

## References

- [trust-service-criteria.md](references/trust-service-criteria.md) — All 5 TSC categories with sub-criteria, control objectives, and evidence examples
- [evidence-collection-guide.md](references/evidence-collection-guide.md) — Evidence types per control, automation approaches, documentation requirements
