---
name: devops-pipeline
description: >
  CI/CD pipeline design following the Three Ways (Gene Kim) and GitOps: build,
  test, deploy stages with blue-green/canary strategies — outputs pipeline
  config, deployment strategy, and monitoring setup. TRIGGER: "devops
  pipeline", "estratégia de deployment", "gitops", "blue-green", "canary",
  "desenha o pipeline", "/dev pipeline". SKIP: quickly generating
  stack-detected GitHub Actions/GitLab CI YAML -> dev/ci-cd-pipeline (the
  generator; this designs the strategy); executing a deploy right now ->
  dev/deploy.
---

# Devops Pipeline

> **Agent:** Carlos (DevOps) | **Framework:** Three Ways (Gene Kim) + GitOps

## What It Does

CI/CD pipeline design: build, test, deploy stages with blue-green/canary strategies.

## Output

Pipeline config (GitHub Actions/GitLab CI), deployment strategy, monitoring setup
