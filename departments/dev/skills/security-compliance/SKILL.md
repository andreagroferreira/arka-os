---
name: dev/security-compliance
description: >
  Security audit preparation, ISMS gap analysis, control assessment, and ISO 27001 certification support for engineering teams.
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

# Security Compliance — `/dev security-compliance`

> **Agent:** Bruno (Security Engineer) | **Framework:** ISO 27001 Audit, ISMS Assessment, ISO 27002

## Audit Readiness Assessment

| Area | What to Verify | Evidence Required |
|------|---------------|-------------------|
| ISMS Scope | Scope document approved, boundaries defined | Signed scope statement |
| Security Policy | Policy current, signed by management, communicated | Signed policy, distribution records |
| Risk Assessment | Methodology defined, assessment completed | Risk register with owners |
| Statement of Applicability | All 93 Annex A controls addressed | SoA document |
| Access Control | Access reviews completed, least privilege enforced | Review logs, access matrices |
| Change Management | All changes authorized, tested, approved | Change tickets, approval records |
| Incident Response | Plan documented, tested, team trained | IR plan, drill reports |
| Business Continuity | DR plan tested, RTO/RPO validated | DR test results |
| Security Awareness | Training completed, phishing tests run | Training records, test results |
| Supplier Security | Vendor assessments current, contracts include security | Assessment reports, DPAs |

## Gap Analysis Workflow

1. **Collect documentation** — Gather all ISMS policies, procedures, and records
2. **Map to clauses** — Verify each ISO 27001 clause (4-10) has documented evidence
3. **Assess Annex A** — Check each applicable control against SoA
4. **Test effectiveness** — Sample controls for operating evidence
5. **Score maturity** — Rate each area (0=Absent, 1=Initial, 2=Managed, 3=Defined, 4=Measured, 5=Optimizing)
6. **Produce gap report** — Prioritized findings with remediation recommendations

## Control Assessment by Domain

### Organizational Controls (A.5)

| Control | Check | Evidence |
|---------|-------|---------|
| A.5.1 Policies | Published, reviewed annually | Policy register, review records |
| A.5.2 Roles | IS responsibilities defined | Job descriptions, RACI |
| A.5.3 Segregation | Conflicting duties separated | Access matrix |
| A.5.23 Cloud security | Cloud usage governed | Cloud security policy |

### Technological Controls (A.8)

| Control | Check | Evidence |
|---------|-------|---------|
| A.8.1 Endpoints | Endpoints protected and managed | EDR dashboard, config |
| A.8.5 Authentication | MFA enforced, strong passwords | IAM config, policy |
| A.8.9 Config management | Baseline configs, hardening | CIS benchmarks, scans |
| A.8.15 Logging | Security events logged centrally | SIEM config, log samples |
| A.8.24 Cryptography | Encryption at rest and transit | TLS config, key management |

## Finding Classification

| Severity | Definition | Response Time | Certification Impact |
|----------|-----------|---------------|---------------------|
| Major NC | Control failure creating significant risk | 30 days | Blocks certification |
| Minor NC | Isolated deviation with limited impact | 90 days | Must resolve before next audit |
| Observation | Improvement opportunity, not a failure | Next audit cycle | Noted, no action required |

## Technical Security Verification

| Area | Automated Check | Tool |
|------|----------------|------|
| Dependencies | Known CVE scan | `npm audit` / `composer audit` / `pip-audit` |
| Secrets | Leaked credentials in code | `gitleaks detect` |
| Infrastructure | Misconfiguration scan | CIS benchmarks, cloud security tools |
| Network | Open ports, TLS config | `nmap`, `testssl.sh` |
| Application | OWASP Top 10 vulnerabilities | DAST/SAST scanners |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Penetration test older than 12 months or never conducted -> flag as A.8.8 control gap requiring immediate scheduling
- Missing security policies (IS policy, access control, acceptable use) -> flag as A.5.1 nonconformity blocking certification
- No incident response plan or plan never tested -> flag as A.5.24-A.5.28 gap creating unmanaged breach risk

## Output

```markdown
## Security Compliance Assessment: <project/organization>

### Overall Maturity: X/5 — <Maturity Level>

### Clause Compliance (ISO 27001)
| Clause | Status | Maturity | Gaps |
|--------|--------|----------|------|

### Annex A Control Status
- Applicable controls: X/93
- Implemented: X | Partial: X | Missing: X

### Critical Findings
- [F1] Severity — Control Ref — Description — Remediation

### Technical Scan Results
- Dependency vulnerabilities: X critical, X high
- Secrets detected: X
- Misconfigurations: X

### Certification Readiness: X%
### Estimated Time to Certification: X months

### Remediation Roadmap
| Priority | Finding | Action | Owner | Target |
|----------|---------|--------|-------|--------|
```

## References

- [iso27001-audit-methodology.md](references/iso27001-audit-methodology.md) — Audit program structure, risk-based scheduling, certification support procedures
- [security-control-testing.md](references/security-control-testing.md) — Technical verification procedures for ISO 27002 controls, evidence requirements
