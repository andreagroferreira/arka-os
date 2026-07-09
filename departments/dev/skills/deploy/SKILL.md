---
name: dev/deploy
description: >
  Deploy to an environment with blue-green/canary strategy: pre-deploy checks,
  deployment execution, and post-deploy verification — outputs a deployment
  report with status, rollback plan, and monitoring links. TRIGGER: "deploy",
  "faz deploy", "ship to staging", "manda para produção", "release to prod",
  "/dev deploy". SKIP: designing the pipeline that automates deploys ->
  dev/ci-cd-pipeline (config generation, not execution); coordinating the
  whole release (versioning, freeze, sign-offs) -> dev/release; production
  failure during rollout -> dev/incident.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Deploy — `/dev deploy <env>`

> **Agent:** Carlos (DevOps) | **Framework:** Blue-Green + Canary Deployments

## What It Does

Deploy to environment: pre-deploy checks, deployment execution, post-deploy verification.

## Output

Deployment report with status, rollback plan, and monitoring links
