---
name: community/platform-select
description: >
  Selects the right community platform for a niche — Telegram, Discord,
  Skool, Circle, Mighty, Whop — via a selection matrix, delivered as a
  recommendation with comparison table and migration plan. TRIGGER: "que
  plataforma para a comunidade", "Discord ou Telegram?", "Skool vs Circle",
  "where should I host my community", "migrar a comunidade de plataforma",
  "/community platform <niche>". SKIP: platform already chosen and needs
  setup -> community/niche-setup (or community/ai-community for AI Discord);
  viability question first -> community/business-model.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Platform Select — `/community platform <niche>`

> **Agent:** Beatriz (Community Strategist) | **Framework:** Platform Selection Matrix

## What It Does

Select the right platform for your niche: Telegram, Discord, Skool, Circle, Mighty, Whop.

## Output

Platform recommendation with comparison table and migration plan
