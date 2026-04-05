---
name: ops/iso27001
description: >
  ISO 27001 ISMS implementation, control mapping, risk treatment planning, and certification audit preparation.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# ISO 27001 ISMS — `/ops iso27001`

> **Agent:** Daniel (Ops Lead) | **Framework:** ISO 27001:2022, ISO 27002:2022, ISMS

## ISMS Implementation Phases

| Phase | Key Activities | Deliverables | Timeline |
|-------|---------------|-------------|----------|
| 1. Context | Define scope, interested parties, internal/external issues | Scope statement, context document | 2-4 weeks |
| 2. Leadership | Security policy, roles, management commitment | IS policy, RACI chart | 1-2 weeks |
| 3. Planning | Risk assessment, risk treatment, objectives | Risk register, treatment plan, SoA | 4-6 weeks |
| 4. Support | Resources, competence, awareness, communication | Training plan, comm matrix | 2-4 weeks |
| 5. Operation | Implement controls, operate processes | Control evidence, procedures | 8-12 weeks |
| 6. Evaluation | Internal audit, management review, monitoring | Audit report, review minutes | 2-4 weeks |
| 7. Improvement | Nonconformity management, continual improvement | CAPA records, improvement log | Ongoing |

## Risk Assessment Methodology

| Step | Activity | Output |
|------|----------|--------|
| 1 | Identify information assets and owners | Asset inventory |
| 2 | Identify threats per asset | Threat catalog |
| 3 | Identify vulnerabilities exploitable by threats | Vulnerability list |
| 4 | Assess likelihood (1-5) and impact (1-5) | Risk scores |
| 5 | Calculate risk level (L x I) | Risk matrix |
| 6 | Determine treatment (mitigate, accept, transfer, avoid) | Risk treatment plan |

### Risk Matrix

| Likelihood / Impact | Negligible (1) | Minor (2) | Moderate (3) | Major (4) | Critical (5) |
|---------------------|---------------|-----------|-------------|-----------|-------------|
| Almost Certain (5) | 5 | 10 | 15 | 20 | 25 |
| Likely (4) | 4 | 8 | 12 | 16 | 20 |
| Possible (3) | 3 | 6 | 9 | 12 | 15 |
| Unlikely (2) | 2 | 4 | 6 | 8 | 10 |
| Rare (1) | 1 | 2 | 3 | 4 | 5 |

**Treatment thresholds:** 1-4 Accept | 5-9 Monitor | 10-15 Mitigate (90 days) | 16-20 Mitigate (30 days) | 21-25 Immediate action

## Annex A Control Categories (ISO 27002:2022)

| Category | Controls | Examples |
|----------|---------|---------|
| Organizational (5-8) | 37 | Policies, roles, asset management, access control |
| People (6) | 8 | Screening, awareness, disciplinary, termination |
| Physical (7) | 14 | Perimeters, entry controls, equipment security |
| Technological (8) | 34 | Endpoint, privileged access, encryption, logging |

## Certification Readiness Checklist

### Stage 1 (Documentation Review)
- [ ] ISMS scope documented and approved
- [ ] Information security policy signed by management
- [ ] Risk assessment methodology defined and executed
- [ ] Statement of Applicability (SoA) completed
- [ ] Risk treatment plan with control mapping
- [ ] Internal audit conducted within past 12 months
- [ ] Management review completed with documented outputs

### Stage 2 (Implementation Audit)
- [ ] All Stage 1 findings resolved
- [ ] ISMS operational for minimum 3 months
- [ ] Controls implemented with evidence of effectiveness
- [ ] Security awareness training completed organization-wide
- [ ] Incident response plan tested
- [ ] Access reviews documented at required frequency
- [ ] Metrics collected and monitored

## Proactive Triggers

Surface these issues WITHOUT being asked:

- ISMS scope undefined or not formally approved -> flag as Clause 4.3 gap blocking certification
- No risk treatment plan linking risks to Annex A controls -> flag as Clause 6.1.3 nonconformity
- Annex A controls not mapped in Statement of Applicability -> flag as Clause 6.1.3(d) requirement

## Output

```markdown
## ISO 27001 Assessment: <organization>

### ISMS Maturity: <Initial | Managed | Defined | Measured | Optimizing>

### Gap Analysis Summary
- Clauses assessed: X/10
- Controls mapped: X/93 (Annex A)
- Gaps identified: X critical, X high, X medium

### Risk Register Summary
- Total risks: X
- Critical/High: X (treatment plans required)
- Accepted: X (with documented rationale)

### Certification Readiness: X% (Stage 1) / X% (Stage 2)

### Remediation Roadmap
| Priority | Gap | Action | Owner | Target |
|----------|-----|--------|-------|--------|

### Next Review: <date>
```

## References

- [iso27001-controls.md](references/iso27001-controls.md) — Full Annex A control list with implementation guidance and evidence requirements
- [risk-assessment-guide.md](references/risk-assessment-guide.md) — Risk methodology, asset classification, threat modeling, risk calculation methods
