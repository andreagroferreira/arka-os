---
name: pm/risk-register
description: >
  Project risk register: identifies risks, scores them on a probability x
  impact matrix, and assigns mitigation strategies and owners, using
  pre-mortem (Gary Klein) to surface failure modes. TRIGGER: "risk
  register", "registo de riscos", "quais os riscos deste projeto", "what
  could go wrong", "faz um pre-mortem do projeto", "/pm risk". SKIP:
  strategic scenario stress-testing of a business bet -> strategy/premortem
  (strategy-level kill analysis, not project risk tracking); mapping people
  who can block the project -> pm/stakeholder-map; security-specific
  threats -> dev/security-audit.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Risk Register — `/pm risk <project>`

> **Agent:** Carolina (Product Manager) | **Framework:** Risk Matrix + Pre-Mortem (Gary Klein)

## What It Does

Risk register: identify, assess probability x impact, define mitigation strategies.

## Output

Risk register with probability/impact matrix, mitigations, and owners
