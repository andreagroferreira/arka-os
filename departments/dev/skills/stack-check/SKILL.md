---
name: dev/stack-check
description: >
  Audit the current tech stack through a 12-Factor lens: framework and runtime
  versions, dependency health, security posture, performance, and upgrade
  paths — outputs a stack health report with upgrade recommendations and risk
  assessment. TRIGGER: "stack check", "audita o stack", "are we outdated",
  "devíamos atualizar o Laravel", "upgrade path", "tech stack review", "/dev
  stack-check". SKIP: CVE/license-focused package analysis ->
  dev/dependency-audit (deps only; stack-check is holistic); accumulated code
  debt scoring -> dev/tech-debt.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Stack Check — `/dev stack-check`

> **Agent:** Paulo (Tech Lead) | **Framework:** 12-Factor App + Stack Analysis

## What It Does

Audit current tech stack: versions, dependencies, security, performance, upgrade paths.

## Evidence for the upgrade path

A recommended upgrade needs more than a changelog. Search the target
version's real configs with `mcp__gh-grep__searchGitHub` using code tokens
from the new API — a config key, an import path, a renamed export — and read
what teams that already migrated had to change. Repos that pin the old
version and never moved are evidence too: an upgrade nobody adopted is a
risk signal, not a neutral one.

## Output

Stack health report with upgrade recommendations and risk assessment
