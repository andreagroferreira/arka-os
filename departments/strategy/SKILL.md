---
name: strat
description: >
  Strategy department. Market analysis, brainstorming, competitive intelligence,
  business planning, SWOT, new ideas evaluation.
  Use when user says "strat", "strategy", "brainstorm", "market", "swot", "idea".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Strategy Department — ARKA OS

Strategic planning, market analysis, and idea evaluation.

## Commands

| Command | Description |
|---------|-------------|
| `/strat brainstorm <topic>` | Structured brainstorming session with multiple perspectives |
| `/strat market <sector>` | Market analysis and opportunity mapping |
| `/strat prospect <sector>` | Client prospecting and lead identification |
| `/strat competitor <url>` | Competitive intelligence deep-dive |
| `/strat swot <business>` | SWOT analysis |
| `/strat evaluate <idea>` | New idea evaluation (pros, cons, risks, ROI) |
| `/strat pivot <direction>` | Evaluate a strategic pivot |
| `/strat roadmap <project>` | Strategic roadmap creation |
| `/strat trends <industry>` | Industry trend analysis |

## Obsidian Output

All strategy output goes to the Obsidian vault at `/Users/andreagroferreira/Documents/Personal/`:

| Content Type | Vault Path |
|-------------|-----------|
| Brainstorm sessions | `WizardingCode/Strategy/Brainstorms/<date> <topic>.md` |
| Market analyses | `WizardingCode/Strategy/Market/<date> <sector>.md` |
| Competitor research | `WizardingCode/Strategy/Competitors/<date> <name>.md` |
| SWOT analyses | `WizardingCode/Strategy/SWOT/<date> <business>.md` |
| Roadmaps | `WizardingCode/Strategy/Roadmaps/<project>.md` |
| Trend reports | `WizardingCode/Strategy/Trends/<date> <industry>.md` |
| Idea evaluations | `WizardingCode/Strategy/Ideas/<date> <idea>.md` |

**Obsidian format:**
```markdown
---
type: report
department: strategy
title: "<title>"
date_created: <YYYY-MM-DD>
tags:
  - "report"
  - "strategy"
  - "<specific-tag>"
---
```

All files use wikilinks `[[]]` for cross-references and kebab-case tags.

## Brainstorming Mode

`/strat brainstorm` launches multiple personas simultaneously:

1. **Visionary** — Thinks big, blue-sky ideas, "what if..."
2. **Pragmatist** — "How do we actually build this? What's the MVP?"
3. **Devil's Advocate** — "Why will this fail? What are we missing?"
4. **Customer Voice** — "Would I pay for this? What problem does it solve?"
5. **Analyst** — "What do the numbers say? What's the market size?"

Each persona responds, then a synthesis combines the best insights.

The brainstorm output is saved to Obsidian with all perspectives documented.

---
*All output: `WizardingCode/Strategy/` — Part of the [[WizardingCode MOC]]*
