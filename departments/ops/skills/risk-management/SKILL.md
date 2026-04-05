---
name: ops/risk-management
description: >
  Enterprise risk identification, assessment, treatment, and monitoring using ISO 31000 and COSO ERM frameworks.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Risk Management — `/ops risk-management`

> **Agent:** Daniel (Ops Lead) | **Framework:** ISO 31000:2018, COSO ERM (2017)

## Risk Management Process (ISO 31000)

| Phase | Activities | Deliverables |
|-------|-----------|-------------|
| 1. Scope & Context | Define objectives, stakeholders, risk criteria | Context statement, risk appetite |
| 2. Risk Identification | Identify sources, events, causes, consequences | Risk register (initial) |
| 3. Risk Analysis | Assess likelihood and impact, determine risk level | Risk scores, risk matrix |
| 4. Risk Evaluation | Compare against criteria, prioritize for treatment | Prioritized risk list |
| 5. Risk Treatment | Select and implement treatment options | Treatment plans, residual risk |
| 6. Monitoring & Review | Track risks, review effectiveness, update register | Updated register, reports |
| 7. Communication | Report to stakeholders, escalate as needed | Risk reports, dashboards |

## Risk Identification Techniques

| Technique | Best For | Output |
|-----------|---------|--------|
| Brainstorming | Broad risk discovery | Raw risk list |
| SWOT Analysis | Strategic risks | Categorized risk themes |
| Checklist Analysis | Known risk categories | Validated risk list |
| Process Flow Analysis | Operational risks | Process-linked risks |
| Scenario Analysis | Emerging/future risks | Scenario-based risk descriptions |
| Root Cause Analysis | Understanding risk drivers | Causal chains |

## Risk Assessment Matrix (5x5)

| Likelihood / Impact | Insignificant (1) | Minor (2) | Moderate (3) | Major (4) | Catastrophic (5) |
|---------------------|-------------------|-----------|-------------|-----------|------------------|
| Almost Certain (5) | 5 Medium | 10 High | 15 High | 20 Critical | 25 Critical |
| Likely (4) | 4 Low | 8 Medium | 12 High | 16 Critical | 20 Critical |
| Possible (3) | 3 Low | 6 Medium | 9 Medium | 12 High | 15 High |
| Unlikely (2) | 2 Low | 4 Low | 6 Medium | 8 Medium | 10 High |
| Rare (1) | 1 Low | 2 Low | 3 Low | 4 Low | 5 Medium |

## Risk Treatment Options

| Strategy | When to Use | Example |
|----------|------------|---------|
| Avoid | Risk exceeds appetite, activity not essential | Cancel project, exit market |
| Mitigate | Risk can be reduced to acceptable level | Add controls, improve processes |
| Transfer | Third party better positioned to manage | Insurance, outsourcing, contracts |
| Accept | Risk within appetite, cost of treatment exceeds benefit | Document rationale, monitor |

## Risk Register Template

| Field | Description |
|-------|------------|
| Risk ID | Unique identifier (R-001) |
| Category | Strategic / Operational / Financial / Compliance / Reputational |
| Description | Clear statement of risk event and consequence |
| Owner | Person accountable for managing the risk |
| Likelihood | 1-5 rating with justification |
| Impact | 1-5 rating with justification |
| Inherent Risk | L x I score before treatment |
| Treatment | Avoid / Mitigate / Transfer / Accept |
| Controls | Specific controls or actions in place |
| Residual Risk | L x I score after treatment |
| Status | Open / In Treatment / Monitored / Closed |
| Review Date | Next scheduled review |

## COSO ERM Components

| Component | Focus | Key Activities |
|-----------|-------|---------------|
| Governance & Culture | Tone at the top | Risk oversight, operating structure, values |
| Strategy & Objective Setting | Risk appetite | Business context, risk appetite, strategy alignment |
| Performance | Risk identification | Identify, assess, prioritize, implement responses |
| Review & Revision | Monitoring | Substantial change assessment, performance review |
| Information & Communication | Reporting | Risk information systems, stakeholder reporting |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Risk register older than 6 months without review -> flag as ISO 31000 Clause 6.7 monitoring gap
- No risk appetite or tolerance defined by leadership -> flag as governance gap blocking effective risk evaluation
- Critical risk identified without documented mitigation plan -> flag as unacceptable exposure requiring immediate treatment

## Output

```markdown
## Risk Assessment: <organization/project>

### Risk Profile Summary
- Total risks identified: X
- Critical: X | High: X | Medium: X | Low: X

### Top 5 Risks
| Rank | Risk | Category | Inherent | Treatment | Residual | Owner |
|------|------|----------|----------|-----------|----------|-------|

### Risk Appetite Alignment
- Risks within appetite: X/X
- Risks exceeding appetite: X (treatment plans required)

### Treatment Plan Status
- Plans defined: X/X critical+high risks
- Controls implemented: X/X
- Effectiveness verified: X/X

### Recommendations
1. [Priority] Action — Timeline — Owner

### Next Review: <date>
```

## References

- [iso31000-guide.md](references/iso31000-guide.md) — ISO 31000 principles, framework, process, risk criteria, treatment selection
- [coso-erm-framework.md](references/coso-erm-framework.md) — COSO ERM components, principles, risk appetite, strategy integration
