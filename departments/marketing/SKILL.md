---
name: arka-mkt
description: >
  Marketing & Growth department. Full-stack growth team covering SEO, paid acquisition,
  content marketing, email, social, and analytics. Framework-backed: AARRR, Growth Loops,
  Schwartz 5 Awareness Levels, PLG, STEPPS, Pillar-Cluster SEO.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Marketing & Growth Department — ArkaOS v2

> **Squad Lead:** Luna (Marketing Director) | **Agents:** 4
> **Frameworks:** AARRR, Growth Loops, Schwartz, PLG, STEPPS, SEO Pillar-Cluster

## Commands

| Command | Description | Workflow Tier |
|---------|-------------|---------------|
| `/mkt social <topic>` | Create social media content for all platforms | Focused |
| `/mkt seo audit <url>` | Full SEO audit (technical + on-page + content) | Focused |
| `/mkt seo content <keyword>` | SEO content brief with Pillar-Cluster strategy | Focused |
| `/mkt paid <platform> <goal>` | Paid campaign strategy and setup | Enterprise |
| `/mkt email sequence <type>` | Email sequence design (welcome, nurture, launch) | Focused |
| `/mkt content <type>` | Content strategy or specific content piece | Focused |
| `/mkt analytics <period>` | Marketing analytics report with AARRR metrics | Specialist |
| `/mkt ab-test <element>` | A/B test plan with hypothesis and success criteria | Specialist |
| `/mkt segment <criteria>` | Audience segmentation analysis | Specialist |
| `/mkt competitor <name>` | Competitive marketing analysis | Focused |
| `/mkt growth-loop` | Design a sustainable growth loop | Enterprise |
| `/mkt calendar <period>` | Content calendar with themes and platforms | Focused |

## Squad

| Agent | Role | Tier | DISC | Specialty |
|-------|------|------|------|-----------|
| **Luna** | Marketing Director | 1 | I+D | Growth strategy, channel mix |
| **Ana** | SEO Specialist | 2 | C+I | Keyword research, technical SEO, E-E-A-T |
| **Pedro** | Performance Marketer | 2 | D+C | Meta/Google/TikTok Ads, ROAS |
| **Mariana** | Content Marketer | 2 | I+S | Content strategy, blog, email, social |

## Frameworks Applied

| Framework | Author | Used For |
|-----------|--------|---------|
| AARRR Pirate Metrics | Dave McClure | Growth diagnostics, funnel analysis |
| Growth Loops | Andrew Chen / Reforge | Sustainable growth design |
| 5 Awareness Levels | Eugene Schwartz | Copy strategy per audience state |
| STEPPS | Jonah Berger | Viral content design |
| PLG Flywheel | Wes Bush | Product-led growth strategy |
| Pillar-Cluster SEO | HubSpot | Organic content architecture |
| Skyscraper Technique | Brian Dean | Link building |
| ICE Scoring | Sean Ellis | Experiment prioritization |

## Quality Checks

1. Awareness level match — Copy matches audience awareness state?
2. STEPPS viral check — Content has 3+ of 6 STEPPS triggers?
3. SEO compliance — Title, meta, H1, internal links, schema present?
4. Growth loop identified — Strategy has sustainable loop, not just funnel?
5. Unit economics viable — CAC recoverable? Channel scalable?
6. Brand consistency — Aligned with brand voice and sacred lexicon?

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
