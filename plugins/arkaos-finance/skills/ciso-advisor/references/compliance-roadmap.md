# Compliance Framework Comparison — Deep Reference

> Companion to `ciso-advisor/SKILL.md`. Framework details, timelines, costs, control overlap, and audit preparation.

## Framework Overview

| Framework | Scope | Mandatory? | Target Market | Certifiable? |
|-----------|-------|-----------|---------------|-------------|
| SOC 2 Type I | Security controls at a point in time | No (market-driven) | US B2B SaaS | Yes (audit report) |
| SOC 2 Type II | Controls operating over 3-12 months | No (market-driven) | US B2B SaaS, Enterprise | Yes (audit report) |
| ISO 27001 | Information security management system | No (market-driven) | Global, enterprise | Yes (certification) |
| GDPR | Personal data protection (EU residents) | Yes (law) | Any company handling EU data | No (compliance, not cert) |
| HIPAA | Protected health information (PHI) | Yes (law, US healthcare) | Healthcare, health tech | No (compliance, not cert) |
| PCI-DSS v4.0 | Cardholder data environment | Yes (contractual) | Any company processing cards | Yes (assessment) |

## Timeline and Cost Estimates

| Framework | Prep Time | Audit/Assessment | Total Timeline | Cost Range (startup) | Cost Range (mid-market) |
|-----------|-----------|-----------------|---------------|---------------------|------------------------|
| SOC 2 Type I | 2-4 months | 1-2 months | 3-6 months | $30K-$80K | $50K-$150K |
| SOC 2 Type II | 6-9 months (incl. observation) | 3-6 month observation | 9-15 months | $50K-$120K | $80K-$250K |
| ISO 27001 | 6-12 months | 2-3 months (Stage 1+2) | 8-15 months | $40K-$100K | $80K-$200K |
| GDPR | 3-6 months (initial) | Ongoing | Continuous | $20K-$60K | $50K-$200K |
| HIPAA | 6-12 months | Ongoing (annual review) | Continuous | $40K-$100K | $100K-$300K |
| PCI-DSS | 3-12 months | Quarterly scans + annual SAQ/ROC | Continuous | $20K-$80K (SAQ) | $100K-$500K (ROC) |

**Cost includes:** GRC platform, auditor fees, consultant fees, remediation. **Does not include:** FTE time, infrastructure changes.

## Recommended Sequencing

```
Phase 0: Security Hygiene (Month 1-2)
  - MFA on all accounts
  - Endpoint protection
  - Automated patching
  - Encrypted backups
  - Access reviews

Phase 1: SOC 2 Type I (Month 3-6)
  - Unlocks: Enterprise sales conversations
  - Effort: Medium
  - ROI: Fastest path to "we're audited"

Phase 2: SOC 2 Type II (Month 6-12)
  - Unlocks: Enterprise deal closures, security questionnaire answers
  - Effort: Medium (observation period)
  - ROI: Most requested by US enterprise buyers

Phase 3: ISO 27001 (Month 12-18)
  - Unlocks: Global enterprise, government contracts
  - Effort: High (ISMS establishment)
  - ROI: International recognition, 3-year certification

Phase 4: Domain-Specific (Month 18+)
  - HIPAA if healthcare
  - PCI-DSS if processing cards directly
  - GDPR (should start in Phase 0 if handling EU data)
```

## Control Overlap Matrix

Implementing one framework gives you progress toward others. Overlap percentage of controls:

| Control Domain | SOC 2 | ISO 27001 | GDPR | HIPAA | PCI-DSS |
|---------------|:-----:|:---------:|:----:|:-----:|:-------:|
| Access control | X | X | X | X | X |
| Encryption (at rest) | X | X | X | X | X |
| Encryption (in transit) | X | X | X | X | X |
| Logging and monitoring | X | X | | X | X |
| Incident response | X | X | X | X | X |
| Vendor management | X | X | X | X | X |
| Change management | X | X | | | X |
| Business continuity | X | X | | X | |
| Data classification | | X | X | X | X |
| Data retention/deletion | | X | X | X | |
| Privacy impact assessment | | | X | X | |
| Breach notification | | | X | X | X |
| Physical security | X | X | | X | X |
| HR security (background checks) | X | X | | X | X |
| Risk assessment | X | X | X | X | X |
| Security awareness training | X | X | X | X | X |

**Key insight:** SOC 2 Type II gives ~60% overlap with ISO 27001 controls. Start with SOC 2, then extend to ISO.

## SOC 2 Trust Service Criteria

| Criteria | Required? | Key Controls |
|----------|-----------|-------------|
| Security (Common Criteria) | Always required | Access control, firewalls, encryption, monitoring |
| Availability | If uptime SLA matters | Redundancy, DR plan, capacity planning |
| Processing Integrity | If data accuracy matters | Input validation, error handling, reconciliation |
| Confidentiality | If handling confidential data | Classification, DLP, encryption, access restrictions |
| Privacy | If handling PII | Consent, data minimization, retention, subject rights |

**Typical first audit:** Security + Availability (most buyer requests).

## Audit Preparation Checklist

### 90 Days Before Audit

- [ ] GRC platform populated with all controls and evidence
- [ ] All policies reviewed and approved within last 12 months
- [ ] Access reviews completed for all critical systems
- [ ] Vulnerability scans current (no critical/high unresolved > 30 days)
- [ ] Penetration test completed within last 12 months
- [ ] Incident response plan tested (tabletop exercise documented)
- [ ] Vendor risk assessments current for Tier 1 vendors
- [ ] Security awareness training completed by all employees
- [ ] Business continuity/DR plan tested within last 12 months
- [ ] Change management logs complete and consistent

### 30 Days Before Audit

- [ ] Evidence collection automated where possible (API pulls from tools)
- [ ] Gap analysis completed -- no open critical gaps
- [ ] Point of contact assigned for each control domain
- [ ] Auditor provided with system description and scope
- [ ] Walkthrough scheduled with auditor for complex controls
- [ ] Exception log documented (any deviations with compensating controls)

### During Audit

- [ ] Respond to auditor requests within 24 hours
- [ ] Provide evidence in organized, labeled format
- [ ] Escalate blockers to compliance lead immediately
- [ ] Track all auditor questions and status in shared document

## Policy Document Inventory

| Policy | SOC 2 | ISO 27001 | GDPR | HIPAA | PCI-DSS |
|--------|:-----:|:---------:|:----:|:-----:|:-------:|
| Information Security Policy | R | R | R | R | R |
| Acceptable Use Policy | R | R | | R | R |
| Access Control Policy | R | R | R | R | R |
| Data Classification Policy | | R | R | R | R |
| Data Retention Policy | | R | R | R | R |
| Incident Response Plan | R | R | R | R | R |
| Business Continuity Plan | R | R | | R | |
| Vendor Management Policy | R | R | R | R | R |
| Change Management Policy | R | R | | | R |
| Encryption Policy | R | R | R | R | R |
| Privacy Policy (external) | | | R | R | |
| Password Policy | R | R | | R | R |
| Physical Security Policy | R | R | | R | R |
| Risk Management Policy | R | R | R | R | R |
| SDLC/Secure Development Policy | R | R | | | R |

**R = Required.** Writing once with framework-agnostic language covers multiple audits.

## GRC Platform Selection

| Platform | Best For | Price Range | Key Feature |
|----------|----------|-------------|------------|
| Vanta | Startups, fast SOC 2 | $10K-$50K/yr | Automated evidence collection |
| Drata | Mid-market, multi-framework | $10K-$50K/yr | Custom controls, integrations |
| Secureframe | Startups, simple setup | $8K-$40K/yr | Fast onboarding |
| Tugboat Logic (OneTrust) | Mid-market | $15K-$60K/yr | Risk management focus |
| OneTrust | Enterprise, privacy-heavy | $50K-$200K/yr | GDPR/privacy specialization |
| Manual (spreadsheets) | <10 employees, one framework | $0 | Pain |

**Decision rule:** If pursuing SOC 2 and have > 15 employees, a GRC platform pays for itself in audit prep time saved.

## Common Compliance Mistakes

| Mistake | Consequence | Fix |
|---------|------------|-----|
| Starting with ISO 27001 before SOC 2 | Longer time to first audit report | SOC 2 Type I first (3-6 months) |
| Policies written but not followed | Audit findings, qualified report | Automate enforcement where possible |
| Annual access reviews only | Stale access, audit gaps | Quarterly for privileged, semi-annual for standard |
| No evidence of control operation | Auditor cannot verify | Automated evidence collection via GRC platform |
| Treating compliance as one-time project | Controls degrade, next audit fails | Continuous monitoring, monthly reviews |
| Scope too broad on first audit | Higher cost, more findings | Start narrow, expand in subsequent years |
