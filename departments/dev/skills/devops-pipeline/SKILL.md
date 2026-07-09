---
name: dev/devops-pipeline
description: >
  CI/CD pipeline design following the Three Ways (Gene Kim) and GitOps: build,
  test, deploy stages with blue-green/canary strategies — outputs pipeline
  config, deployment strategy, and monitoring setup. TRIGGER: "devops
  pipeline", "estratégia de deployment", "gitops", "blue-green", "canary",
  "desenha o pipeline", "/dev pipeline". SKIP: quickly generating
  stack-detected GitHub Actions/GitLab CI YAML -> dev/ci-cd-pipeline (the
  generator; this designs the strategy); executing a deploy right now ->
  dev/deploy.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Devops Pipeline — `/dev pipeline <project>`

> **Agent:** Carlos (DevOps) | **Framework:** Three Ways (Gene Kim) + GitOps

## What It Does

CI/CD pipeline design: build, test, deploy stages with blue-green/canary strategies.

## Output

Pipeline config (GitHub Actions/GitLab CI), deployment strategy, monitoring setup
