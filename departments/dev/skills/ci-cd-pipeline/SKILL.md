---
name: dev/ci-cd-pipeline
description: >
  Design and generate CI/CD pipelines from detected project stack.
  GitHub Actions and GitLab CI with caching, matrix builds, and deployment gates.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# CI/CD Pipeline — `/dev ci-cd-pipeline <project>`

> **Agent:** Andre (Backend Dev) | **Framework:** DevOps Pipeline Design

## What This Does

Detects project stack from repository files, then generates pragmatic CI/CD pipelines with lint, test, build, and deploy stages. Supports GitHub Actions and GitLab CI.

## Stack Detection Heuristics

| Signal | Determines |
|--------|-----------|
| Lockfiles (`composer.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) | Package manager |
| Manifests (`composer.json`, `package.json`, `pyproject.toml`, `go.mod`) | Runtime/language |
| Script commands in manifests | Lint, test, build commands |
| Missing scripts | Conservative placeholder commands |

## Pipeline Stages

| Stage | Purpose | Gate |
|-------|---------|------|
| **Lint** | Code style, static analysis | Must pass before test |
| **Test** | Unit + feature tests | Must pass before build |
| **Build** | Compile, bundle, optimize | Must pass before deploy |
| **Deploy (staging)** | Deploy to staging environment | Explicit environment context |
| **Deploy (production)** | Deploy to production | Manual approval gate required |

## Platform Selection

| Platform | When to Choose |
|----------|---------------|
| **GitHub Actions** | Tight GitHub ecosystem, public repos, most teams |
| **GitLab CI** | Self-hosted SCM + CI, integrated container registry |

Keep one canonical pipeline source per repo to reduce drift.

## Caching Strategy by Stack

| Stack | Cache Key | Cache Path |
|-------|-----------|-----------|
| **Node.js (npm)** | `${{ hashFiles('package-lock.json') }}` | `~/.npm` |
| **Node.js (pnpm)** | `${{ hashFiles('pnpm-lock.yaml') }}` | `~/.pnpm-store` |
| **PHP (Composer)** | `${{ hashFiles('composer.lock') }}` | `vendor/` |
| **Python (pip)** | `${{ hashFiles('requirements.txt') }}` | `~/.cache/pip` |
| **Go** | `${{ hashFiles('go.sum') }}` | `~/go/pkg/mod` |

## Design Checklist

- [ ] Stack detected from lockfiles and manifests
- [ ] Lint, test, build commands verified to exist in project
- [ ] Cache strategy matches package manager
- [ ] Required secrets documented (not embedded in YAML)
- [ ] Branch protection rules match org policy
- [ ] Deploy jobs gated by protected environments
- [ ] Matrix builds only when compatibility truly requires it
- [ ] Pipeline duration tracked as a metric

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Copying a Node pipeline into Python/Go repos | Detect stack first, then generate |
| Deploy jobs before stable tests | Require green CI before deploy |
| Forgetting dependency cache keys | Use lockfile hash as cache key |
| Expensive matrix builds on every branch | Limit matrix to main/release branches |
| Hardcoded secrets in YAML | Use CI secret store, document required vars |
| No rollback plan | Keep rollout/rollback commands explicit |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No caching in CI → flag slow pipeline
- Deploy without smoke test → flag blind deployment
- Secrets in env vars without rotation → flag security risk

## Output

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: <setup-action>
      - run: <install-command>
      - run: <lint-command>

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: <setup-action>
      - run: <install-command>
      - run: <test-command>

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: <setup-action>
      - run: <install-command>
      - run: <build-command>

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: <staging|production>
    runs-on: ubuntu-latest
    steps:
      - run: <deploy-command>
```
