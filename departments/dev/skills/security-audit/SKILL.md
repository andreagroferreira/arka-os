---
name: dev/security-audit
description: >
  OWASP Top 10 (2025) security audit with dependency scanning and security headers check.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Security Audit — `/dev security-audit`

> **Agent:** Bruno (Security Engineer)
> **Framework:** OWASP Top 10 (2025), DevSecOps Pipeline

## OWASP Top 10 (2025) Checklist

| # | Vulnerability | What to Check |
|---|-------------|--------------|
| A01 | Broken Access Control | RBAC/ABAC implemented? Deny by default? |
| A02 | Cryptographic Failures | TLS everywhere? Data encrypted at rest? Strong algorithms? |
| A03 | Supply Chain Failures | Dependencies audited? SBOM exists? Signed artifacts? |
| A04 | Injection | Parameterized queries? Input validation? Output encoding? |
| A05 | Security Misconfiguration | Default credentials removed? Security headers present? |
| A06 | Vulnerable Components | `npm audit` / `composer audit` clean? No known CVEs? |
| A07 | Authentication Failures | MFA available? Rate limiting? Secure session management? |
| A08 | Data Integrity Failures | Deserialization safe? Signed packages? CI/CD tamper-proof? |
| A09 | Logging Failures | Security events logged? Centralized logging? Alerting? |
| A10 | Exceptional Conditions | Secure error handling? No stack traces in production? |

## Security Headers Check

```
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## Automated Scans

| Tool | What | Command |
|------|------|---------|
| npm audit | JS dependency CVEs | `npm audit --production` |
| composer audit | PHP dependency CVEs | `composer audit` |
| pip audit | Python dependency CVEs | `pip-audit` |
| GitLeaks | Secrets in code | `gitleaks detect` |

## Output: Security Report

```markdown
## Security Audit: <project>

### CRITICAL (fix immediately)
- [C1] SQL Injection in UserController:45 — raw query with user input
  Fix: Use parameterized query via Eloquent

### HIGH (fix before release)
- [H1] Missing CSRF protection on /api/webhook endpoint

### MEDIUM
- [M1] npm audit: 2 moderate vulnerabilities in lodash

### LOW
- [L1] Missing Permissions-Policy header

### Summary: 1 critical, 1 high, 1 medium, 1 low
### Recommendation: BLOCK release until C1 and H1 resolved
```

## References

- [owasp-2025-deep.md](references/owasp-2025-deep.md) — OWASP Top 10 (2025) with vulnerable and fixed code examples, testing methodology, and tools
