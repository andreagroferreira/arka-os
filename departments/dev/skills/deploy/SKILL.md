---
name: dev/deploy
description: >
  Deploy to environment: pre-deploy checks, deployment execution, post-deploy verification.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Deploy — `/dev deploy <env>`

> **Agent:** Carlos (DevOps) | **Framework:** Blue-Green + Canary Deployments

## What It Does

Deploy to environment: pre-deploy checks, deployment execution, post-deploy verification.

## Output

Deployment report with status, rollback plan, and monitoring links
