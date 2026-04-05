---
name: ops/quality-management
description: >
  Quality management system design, process improvement, internal audit management, and management review per ISO 9001.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Quality Management — `/ops quality-management`

> **Agent:** Daniel (Ops Lead) | **Framework:** ISO 9001:2015, QMS, PDCA Cycle

## QMS Implementation Phases

| Phase | PDCA | Activities | Deliverables |
|-------|------|-----------|-------------|
| 1. Context & Scope | Plan | Interested parties, scope, process map | Context document, scope statement |
| 2. Leadership | Plan | Quality policy, objectives, roles | Policy, RACI, objectives |
| 3. Planning | Plan | Risk-based thinking, quality objectives | Risk register, action plans |
| 4. Support | Do | Resources, competence, awareness, documentation | Training plan, doc control |
| 5. Operation | Do | Process execution, control of outputs | Procedures, work instructions |
| 6. Evaluation | Check | Monitoring, internal audit, management review | Audit reports, review minutes |
| 7. Improvement | Act | Nonconformity, CAPA, continual improvement | CAPA records, improvement log |

## Quality KPIs Dashboard

| Category | KPI | Target | Calculation |
|----------|-----|--------|------------|
| Process | First Pass Yield | > 95% | (Units passed first / Total) x 100 |
| Process | Nonconformance Rate | < 1% | (NC count / Total) x 100 |
| CAPA | Closure Rate (on-time) | > 90% | (On-time closures / Due) x 100 |
| CAPA | Effectiveness Rate | > 85% | (Effective / Verified) x 100 |
| Audit | Finding Closure Rate | > 90% | (Closed on time / Total due) x 100 |
| Audit | Repeat Finding Rate | < 10% | (Repeats / Total findings) x 100 |
| Customer | Complaint Rate | < 0.1% | (Complaints / Units) x 100 |
| Customer | Satisfaction Score | > 4.0/5.0 | Average survey score |

## Internal Audit Program

| Risk Level | Audit Frequency | Scope |
|-----------|----------------|-------|
| High | Quarterly | Critical processes, customer-facing |
| Medium | Semi-annual | Supporting processes |
| Low | Annual | Administrative processes |

### Audit Workflow
1. Define annual audit schedule based on process risk
2. Assign auditors (independent from audited area)
3. Prepare audit plan and checklist per ISO 9001 clauses
4. Conduct audit: opening meeting, evidence collection, closing
5. Document findings: major NC, minor NC, observation, opportunity
6. Issue corrective action requests with deadlines
7. Verify corrective action effectiveness
8. Report results to management review

## Management Review Inputs (ISO 9001 Clause 9.3.2)

| Input | Source | Required |
|-------|--------|----------|
| Previous review actions | Review records | Yes |
| Changes in external/internal issues | Context monitoring | Yes |
| Customer satisfaction and feedback | Surveys, complaints | Yes |
| Quality objectives achievement | KPI reports | Yes |
| Process performance and product conformity | Process metrics | Yes |
| Nonconformities and corrective actions | CAPA system | Yes |
| Audit results | Internal/external audits | Yes |
| Supplier performance | Supplier scorecards | Yes |
| Improvement opportunities | All sources | Yes |

## CAPA Process

| Step | Activity | Timeline | Owner |
|------|----------|----------|-------|
| 1 | Identify nonconformity or improvement need | Immediate | Anyone |
| 2 | Contain immediate effects | 24-48 hours | Process owner |
| 3 | Root cause analysis (5 Whys, Ishikawa, 8D) | 10 days | CAPA owner |
| 4 | Define corrective/preventive actions | 5 days | CAPA owner |
| 5 | Implement actions | Per plan | Assigned |
| 6 | Verify effectiveness | 30-90 days | Quality |
| 7 | Close and update documentation | 5 days | Quality |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No CAPA process defined or CAPA backlog exceeding SLA -> flag as ISO 9001 Clause 10.2 nonconformity risk
- Management review overdue or not conducted within scheduled period -> flag as Clause 9.3 requirement gap
- No internal audit schedule or audit program not covering all QMS processes -> flag as Clause 9.2 compliance gap

## Output

```markdown
## Quality Management Assessment: <organization>

### QMS Maturity: <Initial | Documented | Implemented | Measured | Optimizing>

### KPI Summary
| KPI | Current | Target | Status |
|-----|---------|--------|--------|

### Audit Program Status
- Audits completed: X/X planned
- Open findings: X (major: X, minor: X)
- Overdue CAPAs: X

### Process Performance
- Processes meeting targets: X/X
- Processes requiring intervention: X

### Recommendations
1. [Priority] Action — Timeline — Owner

### Next Management Review: <date>
```

## References

- [iso9001-implementation.md](references/iso9001-implementation.md) — ISO 9001:2015 clause-by-clause guidance, process approach, documentation requirements
- [capa-methodology.md](references/capa-methodology.md) — Root cause analysis techniques, corrective action planning, effectiveness verification
