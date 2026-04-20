---
name: ops/gdpr-compliance
description: >
  GDPR compliance assessment with data mapping, DPIA generation, breach response planning, and data subject rights management.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# GDPR Compliance — `/ops gdpr-compliance`

> **Agent:** Daniel (Ops Lead) | **Framework:** GDPR (EU 2016/679), Privacy by Design (Cavoukian)

## GDPR Compliance Checklist

| Area | Requirement | GDPR Article | Status |
|------|------------|-------------|--------|
| Legal Basis | Documented lawful basis for each processing activity | Art. 6 | [ ] |
| Consent | Freely given, specific, informed, unambiguous | Art. 7 | [ ] |
| Data Mapping | Records of processing activities maintained | Art. 30 | [ ] |
| DPIA | Impact assessment for high-risk processing | Art. 35 | [ ] |
| DPO | Data Protection Officer appointed (if required) | Art. 37 | [ ] |
| Subject Rights | Process for access, rectification, erasure, portability | Art. 15-20 | [ ] |
| Breach Response | 72-hour notification procedure documented | Art. 33 | [ ] |
| Transfers | Adequate safeguards for international data transfers | Art. 46 | [ ] |
| Privacy by Design | Data protection integrated into system design | Art. 25 | [ ] |
| Retention | Data retention and deletion policies defined | Art. 5(1)(e) | [ ] |

## Data Mapping Template

| Processing Activity | Data Categories | Data Subjects | Legal Basis | Retention | Recipients | Transfers |
|---------------------|----------------|---------------|-------------|-----------|------------|-----------|
| User registration | Name, email | Customers | Contract | Account lifetime + 1yr | Internal | None |
| Newsletter | Email, preferences | Subscribers | Consent | Until withdrawal | Mailchimp | US (SCCs) |
| Analytics | IP, behavior | Visitors | Legitimate interest | 26 months | Google | US (SCCs) |

## DPIA Decision Criteria

A DPIA is **required** when processing involves:

| Criterion | Example | WP29 Reference |
|-----------|---------|----------------|
| Systematic monitoring | Employee tracking, CCTV | Art. 35(3)(c) |
| Large-scale special data | Health records platform | Art. 35(3)(b) |
| Automated decisions with legal effects | Credit scoring, hiring AI | Art. 35(3)(a) |
| Combining datasets | CRM + analytics merge | WP248 criterion 4 |
| Vulnerable data subjects | Children, employees | WP248 criterion 7 |
| New technology | Biometrics, AI profiling | WP248 criterion 8 |

## Data Subject Rights — Response Workflow

| Right | Article | Deadline | Extensions |
|-------|---------|----------|------------|
| Access | Art. 15 | 30 days | +60 days (complex) |
| Rectification | Art. 16 | 30 days | +60 days (complex) |
| Erasure ("Right to be Forgotten") | Art. 17 | 30 days | +60 days (complex) |
| Restriction | Art. 18 | 30 days | +60 days (complex) |
| Portability | Art. 20 | 30 days | +60 days (complex) |
| Objection | Art. 21 | 30 days | N/A |

## Breach Response Procedure

1. **Detect and contain** — Isolate affected systems, preserve evidence
2. **Assess severity** — Personal data types, number of subjects, likely harm
3. **Notify authority** — Within 72 hours if risk to rights/freedoms (Art. 33)
4. **Notify data subjects** — Without undue delay if high risk (Art. 34)
5. **Document** — Record breach details, effects, remedial actions taken
6. **Review** — Update risk assessment and preventive controls

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Personal data processing without DPIA documented -> flag as GDPR Art. 35 violation risk
- No DPO appointed when processing triggers mandatory designation -> flag as Art. 37 compliance gap
- Data retention policy missing or undefined for processing activities -> flag as Art. 5(1)(e) breach risk

## Output

```markdown
## GDPR Compliance Assessment: <organization/project>

### Compliance Score: X/10

### Critical Gaps
- [CG1] Description — Art. X reference — Remediation steps

### Data Mapping Summary
- Processing activities documented: X
- Legal bases verified: X/X
- International transfers: X (safeguards: Y/N)

### DPIA Status
- Required: Y/N — Reason: [criteria]
- Completed: Y/N

### Recommendations
1. [Priority] Action — Timeline — Owner

### Next Review: <date>
```

## References

- [gdpr-compliance-guide.md](references/gdpr-compliance-guide.md) — Legal bases, special category data, accountability requirements, breach notification procedures
- [dpia-methodology.md](references/dpia-methodology.md) — DPIA threshold assessment, risk methodology, mitigation categories, consultation process
