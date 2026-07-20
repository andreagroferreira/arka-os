---
name: ops/lean-audit-skill
description: >
  Runs a Lean audit: maps the value stream, identifies the 7 wastes, and calculates
  waste-elimination ROI into an improvement roadmap. TRIGGER: "auditoria lean", "lean
  audit", "elimina desperdício", "value stream map", "este processo tem muito
  desperdício", "/ops lean-audit". SKIP: diagnosing one choke point -> ops/bottleneck-find
  (single constraint via Theory of Constraints, not a full waste sweep); ISO 9001 quality
  system, CAPA and internal audits -> ops/quality-management.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Lean Audit Skill — `/ops lean-audit`

> **Agent:** Daniel (Ops Lead) | **Framework:** Lean Thinking (Womack) + 7 Wastes

## What It Does

Lean audit: value stream map, identify 7 wastes, calculate waste elimination ROI.

## Output

Lean audit report with value stream map and waste elimination roadmap
