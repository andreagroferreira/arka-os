---
name: ops/integration-design
description: >
  Designs system-to-system integrations via API, webhook, or iPaaS platform, producing a
  spec with data flow diagram, error handling, and monitoring. TRIGGER: "integra o
  sistema X com Y", "connect these two systems", "liga o CRM ao ERP", "integration
  between", "webhook design", "/ops integration <systems>". SKIP: designing the API
  contract itself -> dev/api-design (endpoint design, not cross-system wiring); building
  the flow on an already-chosen platform -> ops/n8n-flow or ops/zapier-flow.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Integration Design — `/ops integration <systems>`

> **Agent:** Tomas A. (Automation Engineer) | **Framework:** iPaaS Architecture + API Patterns

## What It Does

Integration design: connect systems via API, webhook, or iPaaS platform.

## Output

Integration spec with data flow diagram, error handling, and monitoring
