---
name: dev/dependency-audit
description: >
  Audit project dependencies for vulnerabilities, license compliance, outdated packages, and supply chain risks.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Dependency Audit — `/dev dependency-audit`

> **Agent:** Bruno (Security Engineer) | **Framework:** OWASP Supply Chain Security, SemVer

## Audit Scope

| Check | What | Tools |
|-------|------|-------|
| **Vulnerabilities** | Known CVEs in direct and transitive deps | `npm audit`, `composer audit`, `pip-audit`, `cargo audit` |
| **Licenses** | Incompatible or copyleft licenses | `license-checker`, manifest inspection |
| **Outdated** | Packages behind latest stable version | `npm outdated`, `composer outdated` |
| **Unused** | Declared but never imported | `depcheck`, import analysis |
| **Maintenance** | Abandoned or unmaintained packages | Last release date, commit activity |

## Vulnerability Scanning

Run these per ecosystem:

| Ecosystem | Command | Lock File |
|-----------|---------|-----------|
| Node.js | `npm audit --production` | package-lock.json |
| PHP | `composer audit` | composer.lock |
| Python | `pip-audit` | requirements.txt / poetry.lock |
| Go | `govulncheck ./...` | go.sum |
| Rust | `cargo audit` | Cargo.lock |

**Severity classification:**
- **Critical/High** -- Fix before next deploy
- **Medium** -- Fix within current sprint
- **Low** -- Fix within next 30 days

## License Compliance Matrix

| License | Type | Commercial Use | Distribution Risk |
|---------|------|---------------|-------------------|
| MIT, ISC, BSD-2, BSD-3 | Permissive | Safe | None |
| Apache 2.0 | Permissive | Safe | Patent clause |
| MPL 2.0, LGPL | Weak copyleft | Caution | File-level copyleft |
| GPL v2/v3 | Strong copyleft | Risk | Entire project must be GPL |
| AGPL v3 | Network copyleft | High risk | Network use triggers copyleft |
| Proprietary / Unknown | Restricted | Review required | Legal review mandatory |

**Rules:**
- [ ] No GPL/AGPL in proprietary projects
- [ ] All dependencies have identifiable licenses
- [ ] License changes between versions reviewed

## Upgrade Risk Assessment

| Update Type | Risk | Action |
|-------------|------|--------|
| Patch (1.2.3 -> 1.2.4) | Low | Auto-update, run tests |
| Minor (1.2.3 -> 1.3.0) | Medium | Review changelog, run tests |
| Major (1.2.3 -> 2.0.0) | High | Read migration guide, plan sprint work |
| Deprecated | Critical | Find replacement, schedule migration |

## Supply Chain Checks

- [ ] Lock files committed and up to date
- [ ] No typosquatting risks (verify package names)
- [ ] Check for recent maintainer changes on critical deps
- [ ] Verify package registry sources (no unknown registries)
- [ ] Review transitive dependency tree depth (flag > 5 levels)

## Audit Cadence

| Check | Frequency |
|-------|-----------|
| Vulnerability scan | Every CI run |
| License audit | Weekly / before release |
| Outdated check | Monthly |
| Full dependency audit | Quarterly |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Critical CVE in production dependency → BLOCK until resolved
- GPL dependency in commercial project → flag license violation risk
- Dependency with no maintainer activity >1yr → flag supply chain risk

## Output

```markdown
## Dependency Audit: <project>

### Ecosystem: {Node.js / PHP / Python / etc.}
- Direct dependencies: {count}
- Transitive dependencies: {count}

### Vulnerabilities
| Package | Severity | CVE | Fix Version | Status |
|---------|----------|-----|-------------|--------|

### License Issues
| Package | License | Risk | Action Required |
|---------|---------|------|-----------------|

### Outdated (top 10 by age)
| Package | Current | Latest | Type | Risk |
|---------|---------|--------|------|------|

### Unused Dependencies
- [list of packages declared but not imported]

### Summary
- Vulnerabilities: {critical} critical, {high} high, {medium} medium
- License issues: {count}
- Outdated: {count} ({major} major updates pending)
- Recommendation: {SAFE TO DEPLOY | FIX BEFORE DEPLOY | BLOCK DEPLOY}
```

## References

- [license-matrix.md](references/license-matrix.md) — Open source license compatibility matrix, copyleft obligations, commercial use implications, and dual-licensing strategies
