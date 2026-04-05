# GitHub Actions Best Practices — Deep Reference

> Companion to `ci-cd-pipeline/SKILL.md`. Patterns, pitfalls, and production-ready snippets.

## Caching Strategies by Ecosystem

| Ecosystem | Action | Cache Key | Cache Path | Restore Key Fallback |
|-----------|--------|-----------|------------|---------------------|
| Node (npm) | `actions/setup-node@v4` | `node-${{ runner.os }}-${{ hashFiles('package-lock.json') }}` | `~/.npm` | `node-${{ runner.os }}-` |
| Node (pnpm) | `pnpm/action-setup@v4` | `pnpm-${{ runner.os }}-${{ hashFiles('pnpm-lock.yaml') }}` | `~/.pnpm-store` | `pnpm-${{ runner.os }}-` |
| Node (yarn) | `actions/setup-node@v4` | `yarn-${{ runner.os }}-${{ hashFiles('yarn.lock') }}` | `~/.yarn/cache` | `yarn-${{ runner.os }}-` |
| PHP | `shivammathur/setup-php@v2` | `php-${{ runner.os }}-${{ hashFiles('composer.lock') }}` | `vendor/` | `php-${{ runner.os }}-` |
| Python | `actions/setup-python@v5` | `pip-${{ runner.os }}-${{ hashFiles('requirements*.txt') }}` | `~/.cache/pip` | `pip-${{ runner.os }}-` |
| Go | `actions/setup-go@v5` | `go-${{ runner.os }}-${{ hashFiles('go.sum') }}` | `~/go/pkg/mod` | `go-${{ runner.os }}-` |
| Rust | `actions/cache@v4` | `cargo-${{ runner.os }}-${{ hashFiles('Cargo.lock') }}` | `~/.cargo/registry, target/` | `cargo-${{ runner.os }}-` |
| Docker | `docker/build-push-action@v5` | Registry cache or `actions/cache` | `/tmp/.buildx-cache` | Use `mode=max` for layer reuse |

### Cache Size Limits

- Max 10 GB per repository (LRU eviction after 7 days unused)
- Single cache entry max: 10 GB
- If builds are slow, check cache hit rate in Actions UI

## Matrix Builds

### When to Use Matrix

| Situation | Matrix? | Why |
|-----------|---------|-----|
| Library supporting multiple runtimes | Yes | Must verify compatibility |
| Application with fixed runtime | No | One version in production, test that |
| Cross-platform CLI tool | Yes | OS-specific behavior matters |
| PR from feature branch | Minimal | Full matrix on main only (saves minutes) |

### Smart Matrix Pattern

```yaml
strategy:
  fail-fast: true
  matrix:
    include:
      - os: ubuntu-latest
        node: 20
        full-suite: true      # Only run slow tests on primary
      - os: ubuntu-latest
        node: 18
        full-suite: false
      - os: windows-latest
        node: 20
        full-suite: false
```

### Conditional Matrix Expansion

```yaml
# Full matrix on main, minimal on PRs
jobs:
  test:
    strategy:
      matrix:
        node: ${{ github.ref == 'refs/heads/main' && fromJson('[18, 20, 22]') || fromJson('[20]') }}
```

## Reusable Workflows

### When to Extract

- Same CI logic in 3+ repositories
- Org-wide policy (security scanning, deployment gates)
- Shared infrastructure steps (Docker build, cloud deploy)

### Caller Pattern

```yaml
# .github/workflows/ci.yml (caller)
jobs:
  ci:
    uses: org/shared-workflows/.github/workflows/node-ci.yml@v1
    with:
      node-version: 20
      run-e2e: true
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### Versioning Reusable Workflows

| Strategy | Stability | Flexibility |
|----------|-----------|------------|
| `@v1` (major tag) | High | Auto-get patches |
| `@v1.2.3` (exact) | Highest | Must bump manually |
| `@main` | Low | Always latest (dangerous) |
| `@sha` | Highest | Immutable, hard to read |

**Recommendation:** Use `@v1` (major tag), pin to SHA in security-critical pipelines.

## Secret Management

### Secret Scoping

| Scope | Access | Use Case |
|-------|--------|----------|
| Repository secret | This repo only | App-specific keys |
| Environment secret | Gated by environment rules | Production credentials |
| Organization secret | All/selected repos | Shared registry tokens |

### Secret Hygiene Checklist

- [ ] Never echo secrets in logs (`add-mask` for dynamic values)
- [ ] Use environment protection rules for production secrets
- [ ] Rotate secrets on a schedule (90 days max)
- [ ] Scope secrets to specific environments, not repo-wide
- [ ] Use OIDC instead of long-lived credentials for cloud providers

### OIDC for Cloud Providers (No Stored Secrets)

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/deploy
      aws-region: eu-west-1
```

Supported: AWS, GCP, Azure, HashiCorp Vault, Cloudflare.

## Deployment Environments

### Environment Protection Rules

| Rule | Purpose | When |
|------|---------|------|
| Required reviewers | Human approval gate | Production deploys |
| Wait timer | Cooldown between stages | Canary + production |
| Branch restriction | Only main can deploy | Prevent feature-branch deploys |
| Custom deployment rules | Third-party gates (Datadog, PagerDuty) | Status checks before deploy |

### Deployment Strategy Pattern

```yaml
deploy-staging:
  environment: staging
  needs: [test, build]
  # Auto-deploy, no approval needed

deploy-production:
  environment: production   # Has required reviewers
  needs: deploy-staging
  if: github.ref == 'refs/heads/main'
```

## Common Pitfalls and Fixes

| Pitfall | Impact | Fix |
|---------|--------|-----|
| `actions/checkout` without `fetch-depth: 0` | Shallow clone breaks git history tools | Set `fetch-depth: 0` for changelog/versioning |
| Cache key without OS prefix | Cross-OS cache corruption | Always include `runner.os` in key |
| `pull_request_target` with checkout of PR code | Critical security: runs with write access on untrusted code | Use `pull_request` event instead |
| No `concurrency` group | Parallel deploys to same environment | Add `concurrency: { group: deploy-${{ github.ref }} }` |
| Artifact upload without retention | Storage bloat, hitting limits | Set `retention-days: 7` (or less) |
| `continue-on-error: true` hiding failures | Silent breakage | Use only for optional/informational steps |
| Running on `push` to all branches | Wasted minutes | Restrict to `main`, `develop`, use `pull_request` for branches |
| Hardcoded action versions (`@master`) | Breaking changes without notice | Pin to `@v1` or SHA |

## Workflow Performance Optimization

| Technique | Savings | Complexity |
|-----------|---------|------------|
| Dependency caching | 30-60% of install time | Low |
| Path-based triggers | Skip irrelevant jobs | Low |
| Parallel jobs (no `needs`) | Total time = slowest job | Low |
| Larger runners (org-hosted) | 2-4x faster builds | Medium |
| Docker layer caching | 50-80% of build time | Medium |
| Composite actions for shared steps | DRY, faster authoring | Medium |
| Self-hosted runners | No queue wait, persistent cache | High |

### Path-Based Triggers

```yaml
on:
  push:
    paths:
      - 'src/**'
      - 'tests/**'
      - 'package.json'
    paths-ignore:
      - 'docs/**'
      - '*.md'
```

## Security Hardening

- [ ] Pin all third-party actions to full SHA (not tag)
- [ ] Use `permissions` block with minimal scopes
- [ ] Never use `pull_request_target` with PR code checkout
- [ ] Enable `CODEOWNERS` for `.github/workflows/`
- [ ] Audit third-party actions before adoption
- [ ] Use `concurrency` to prevent parallel deploys
