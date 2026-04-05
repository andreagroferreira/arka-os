---
name: dev/env-secrets
description: >
  Audit .env files for leaked secrets, validate .env.example sync, and guide vault integration.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Env & Secrets Manager — `/dev env-secrets`

> **Agent:** Bruno (Security Engineer) | **Framework:** OWASP Secrets Management, DevSecOps

## What It Does

Audits environment files for leaked secrets, validates .env/.env.example drift, and provides vault integration guidance for production workloads.

## Audit Checklist

| Check | What to Verify | Severity |
|-------|---------------|----------|
| .gitignore | `.env` listed and not tracked | CRITICAL |
| Hardcoded secrets | API keys, passwords, tokens in source code | CRITICAL |
| .env.example sync | All keys present with placeholder values, no real values | HIGH |
| Secret patterns | AWS keys, Stripe keys, JWT secrets, DB passwords | CRITICAL |
| Git history | Secrets ever committed (even if removed) | HIGH |
| CI/CD variables | Secrets masked and scoped to environments | MEDIUM |

## Secret Detection Patterns

| Pattern | Regex | Example Match |
|---------|-------|--------------|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| Stripe Key | `sk_(live\|test)_[0-9a-zA-Z]{24,}` | `sk_live_abc123...` |
| JWT Secret | `(jwt\|JWT).*(secret\|key).*=.+` | `JWT_SECRET=mysecret` |
| Generic Password | `(password\|passwd\|pwd).*=.{8,}` | `DB_PASSWORD=hunter2` |
| Private Key | `-----BEGIN (RSA\|EC\|DSA) PRIVATE KEY-----` | PEM block |

## Automated Scans

| Tool | Purpose | Command |
|------|---------|---------|
| GitLeaks | Scan repo for secrets | `gitleaks detect --source . --report-path gitleaks.json` |
| detect-secrets | Baseline + audit | `detect-secrets scan > .secrets.baseline` |
| git log | History check | `git log --all --diff-filter=A -- '*.env' '*secret*'` |

## Vault Integration Guide

| Provider | Best For | Integration Pattern |
|----------|----------|-------------------|
| HashiCorp Vault | Multi-cloud / hybrid | SDK pull or sidecar injection |
| AWS Secrets Manager | AWS-native | Lambda/ECS native, auto-rotation |
| Azure Key Vault | Azure-native | Managed HSM, Azure AD RBAC |
| GCP Secret Manager | GCP-native | IAM-based, automatic versioning |

## Emergency Rotation Checklist

- [ ] Revoke compromised credential immediately at provider
- [ ] Generate and deploy replacement to all consumers
- [ ] Audit access logs for unauthorized usage
- [ ] Scan git history, CI logs, artifacts for leaked value
- [ ] File incident report with scope and timeline
- [ ] Tighten detection controls to prevent recurrence

## Proactive Triggers

Surface these issues WITHOUT being asked:

- .env file in git history → CRITICAL flag, rotation needed
- Hardcoded API key in source → BLOCK until removed
- Secrets without expiration → flag rotation risk

## Output

```markdown
## Env & Secrets Audit: <project>

### CRITICAL
- [C1] `.env` committed to git — contains DB_PASSWORD and STRIPE_KEY
  Fix: Remove from tracking, rotate credentials, add to .gitignore

### HIGH
- [H1] .env.example missing 3 keys present in .env
- [H2] AWS key found in git history (commit abc123)

### MEDIUM
- [M1] CI secrets not scoped to production environment

### Rotation Required: DB_PASSWORD, STRIPE_KEY, AWS_ACCESS_KEY_ID
### Recommendation: BLOCK deploy until all CRITICAL items resolved
```
