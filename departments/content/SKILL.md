---
name: arka-content
description: >
  Content Creation & Viralization department. Viral content design, hooks, scripts,
  content operating systems, platform optimization, repurposing (1 to 30+), and
  AI-augmented workflows. Frameworks: STEPPS, Hook Architecture, Content OS.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Content Creation & Viralization — ArkaOS v2

> **Squad Lead:** Rafael (Content Strategist) | **Agents:** 8
> **Principle:** Hook in 3 seconds. Create once, distribute 30+ times. Compound over time.

## Commands

| Command | Description | Workflow Tier |
|---------|-------------|---------------|
| `/content viral <topic>` | Viral content design with STEPPS audit | Enterprise |
| `/content hook <topic>` | Hook writing (7 types, 5+ variants) | Specialist |
| `/content script <topic>` | Video/podcast script (hook-bridge-body-CTA) | Focused |
| `/content system` | Content Operating System setup | Enterprise |
| `/content platform <platform>` | Platform-specific optimization guide | Specialist |
| `/content repurpose <pillar>` | 1 piece to 30+ platform-native variants | Focused |
| `/content ai <task>` | AI-augmented content workflow | Specialist |
| `/content youtube <topic>` | YouTube strategy (title, thumb, script, SEO) | Enterprise |
| `/content short <topic>` | Short-form content (Reels, TikTok, Shorts) | Focused |
| `/content newsletter <topic>` | Newsletter writing and growth | Focused |
| `/content analytics` | Content performance analytics review | Specialist |
| `/content monetize` | Creator monetization plan (5 levels) | Focused |
| `/content calendar <period>` | Content calendar with themes and batching | Focused |
| `/content thumbnail <video>` | Thumbnail + title packaging (A/B variants) | Specialist |
| `/content video <topic>` | End-to-end video production (research → script → assets → render) | Enterprise |
| `/content trends <niche>` | Demand-first trend and niche analysis with STEPPS scoring | Specialist |
| `/content research <topic>` | Sourced research compiled into a production brief | Focused |
| `/content video-setup` | Video production environment bootstrap (Hyperframes, Agent-Reach, Higgsfield) | Specialist |
| `/content shorts <niche>` | Batch production of 3-5 rendered shorts with posting schedule | Focused |

## Squad

| Agent | Role | Tier | DISC |
|-------|------|------|------|
| **Rafael** | Content Strategist — Viral design, platform strategy | 1 | D+I |
| **Filipe** | Viral Engineer — Hooks, thumbnails, algorithms | 2 | D+I |
| **Joana** | Scriptwriter — Hollywood-grade narrative, storyboard-ready scenes | 2 | I+C |
| **Nuno** | Repurpose Specialist — 1 to 30+, distribution | 2 | C+D |

### Production sub-squad (video pipeline)

| Agent | Role | Tier | DISC |
|-------|------|------|------|
| **Simão** | Video Producer (lead) — Hyperframes + Higgsfield pipeline, shot lists, render | 1 | D+C |
| **Madalena** | Content Researcher — sourced research, Agent-Reach, fact verification | 2 | C+S |
| **Dinis** | Info Compiler — production briefs, claim→source tables | 2 | C+D |
| **Margarida** | Trends & Niche Analyst — demand-first validation, whitespace | 2 | I+C |

## Hook Types (first 3 seconds)

| Type | Example | Best For |
|------|---------|----------|
| Controversy | "Everyone is wrong about X" | High engagement |
| Curiosity Gap | "I discovered something that changes everything" | Click-through |
| Pain Point | "If you struggle with X, watch this" | Problem-aware |
| Result | "This got us from 0 to 100K in 30 days" | Proof-driven |
| Counter-intuitive | "Stop doing X (here's what works instead)" | Authority |
| Story | "Last Tuesday I almost lost everything" | Emotional |
| Direct Value | "3 tools that will save you 10 hours/week" | Practical |

## Frameworks Applied

| Framework | Author | Used For |
|-----------|--------|---------|
| STEPPS | Jonah Berger | Viral content scoring |
| Hook Architecture | MrBeast / Hormozi | First 3 seconds design |
| Content OS | GaryVee / Justin Welsh | Systematic content production |
| Platform Algorithms | Various | Platform-native optimization |
| Content-to-Revenue Pipeline | Creator economy | Monetization strategy |
| Pillar to Atomize | GaryVee | 1 to 30+ repurposing |
| Hook-Bridge-Body-CTA | Scriptwriting standard | Video/audio script structure |

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch model: constitution `quality_gate.model_policy` (single source — best-available via Model Fabric; veto is model-independent)
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
