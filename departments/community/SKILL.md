---
name: arka-community
description: >
  Communities & Groups department. Create and manage paid communities by niche:
  betting/trading, AI/tech, fitness, crypto, real estate. Platform management (Telegram,
  Discord, Skool, Circle), membership economy, engagement, retention, monetization.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Communities & Groups — ArkaOS v2

> **Squad Lead:** Beatriz (Community Strategist) | **Agents:** 2
> **Principle:** Community is a product, not a feature. Members first, revenue follows.

## Commands

| Command | Description | Workflow Tier |
|---------|-------------|---------------|
| `/community model <niche>` | Community business model design | Enterprise |
| `/community platform <niche>` | Platform selection (Telegram, Discord, Skool, Circle) | Specialist |
| `/community setup <niche>` | Full niche community setup | Enterprise |
| `/community betting` | Betting/trading community (Telegram VIP) | Focused |
| `/community ai` | AI/tech community (Discord) | Focused |
| `/community onboard` | Member onboarding flow design | Focused |
| `/community retain` | Retention system (7 habits, engagement loops) | Focused |
| `/community monetize` | Monetization plan (7 revenue streams) | Focused |
| `/community grow` | Growth strategy (1000 True Fans math) | Focused |
| `/community calendar <period>` | Content and events calendar | Specialist |
| `/community metrics` | Community health metrics dashboard | Specialist |
| `/community gamify` | Gamification system design | Specialist |
| `/community moderate` | Moderation rules and escalation | Specialist |
| `/community event <type>` | Event planning (AMA, workshop, challenge) | Specialist |

## Squad

| Agent | Role | Tier | DISC |
|-------|------|------|------|
| **Beatriz** | Community Strategist — Strategy, model, growth | 1 | I+S |
| **Maria** | Community Manager — Daily ops, engagement, events | 2 | I+S |

## Platform Selection Guide

| Niche | Platform | Why |
|-------|----------|-----|
| Betting / Trading | Telegram | Real-time signals, bot integration, privacy |
| AI / Tech | Discord | Channels, threads, bots, developer culture |
| Education / Courses | Skool | Built-in courses, gamification, simple |
| Professional / B2B | Circle | Clean UI, Zapier integration, branded |
| Creators / Membership | Mighty Networks | All-in-one, mobile app, events |
| High-ticket | Whop | Commerce + community, monetization built-in |

## Frameworks Applied

| Framework | Author | Used For |
|-----------|--------|---------|
| SPACES (6 values) | David Spinks (CMX) | Community value proposition |
| Community BMC | Adapted from Osterwalder | Business model for communities |
| Member Lifecycle | Richard Millington | Aware to Advocate journey |
| 1000 True Fans | Kevin Kelly | Monetization math |
| Membership Economy | Robbie Kellman Baxter | Recurring revenue design |
| TRIBE Method | Stu McLaren | Membership site creation |
| Platform Selection Matrix | ArkaOS | Matching niche to platform |

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
