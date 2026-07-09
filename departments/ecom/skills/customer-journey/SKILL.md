---
name: ecom/customer-journey
description: >
  Maps the e-commerce customer journey across discovery, consideration,
  purchase, delivery, and loyalty stages, producing a journey map with
  touchpoints, pain points, and optimization opportunities per stage. TRIGGER:
  "jornada do cliente", "mapeia a experiência do cliente", "customer journey
  map", "touchpoints da loja", "/ecom journey <segment>". SKIP: scoring
  customers by purchase behaviour -> ecom/rfm-segment (data segmentation, not
  experience mapping); fixing a specific conversion drop-off
  -> ecom/cro-optimize (research and testing, not mapping).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Customer Journey — `/ecom journey <segment>`

> **Agent:** Catarina (Retention Manager) | **Framework:** Customer Lifecycle + RFM

## What It Does

Customer journey mapping: discovery, consideration, purchase, delivery, loyalty.

## Output

Journey map with touchpoints, pain points, and optimization opportunities per stage
