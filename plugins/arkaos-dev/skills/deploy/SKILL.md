---
name: deploy
description: >
  Deploy to an environment with blue-green/canary strategy: pre-deploy checks,
  deployment execution, and post-deploy verification — outputs a deployment
  report with status, rollback plan, and monitoring links. TRIGGER: "deploy",
  "faz deploy", "ship to staging", "manda para produção", "release to prod",
  "/dev deploy". SKIP: designing the pipeline that automates deploys ->
  dev/ci-cd-pipeline (config generation, not execution); coordinating the
  whole release (versioning, freeze, sign-offs) -> dev/release; production
  failure during rollout -> dev/incident.
---

# Deploy

> **Agent:** Carlos (DevOps) | **Framework:** Blue-Green + Canary Deployments

## What It Does

Deploy to environment: pre-deploy checks, deployment execution, post-deploy verification.

## Output

Deployment report with status, rollback plan, and monitoring links
