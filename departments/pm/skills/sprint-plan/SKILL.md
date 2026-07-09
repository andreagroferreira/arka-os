---
name: pm/sprint-plan
description: >
  Scrum sprint planning (Scrum Guide 2020): selects backlog items, defines
  the sprint goal, checks team capacity, and locks the commitment with a
  definition of done. TRIGGER: "planeia o sprint", "plan the sprint",
  "sprint planning", "o que entra no próximo sprint", "define o sprint
  goal", "/pm sprint". SKIP: items not yet refined or prioritized ->
  pm/backlog-groom (groom before you plan); continuous-flow teams without
  sprints -> pm/kanban-setup; multi-sprint delivery forecasting ->
  pm/estimate-forecast.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Sprint Plan — `/pm sprint <action>`

> **Agent:** Jorge (Scrum Master) | **Framework:** Scrum Guide 2020 (Sutherland)

## What It Does

Sprint planning: select items, define sprint goal, capacity check, commitment.

## Output

Sprint plan with goal, selected items, capacity, and definition of done
