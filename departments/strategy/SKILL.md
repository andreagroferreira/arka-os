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

## Workflows

### /strat brainstorm <topic>

**Step 1: Frame the Topic**
- Clarify the question or opportunity being explored
- Define scope and constraints (budget, timeline, resources)

**Step 2: Run 5 Perspective Agents in Parallel**

Launch these agents simultaneously:

**Agent 1: Visionary**
- "What if we could...?"
- Blue-sky thinking, no constraints
- 10x ideas, moonshots, paradigm shifts
- Adjacent industry inspiration

**Agent 2: Pragmatist**
- "Here's how we'd actually build this..."
- MVP definition, resource requirements
- Timeline estimation, phased rollout
- Technical feasibility assessment

**Agent 3: Devil's Advocate**
- "Why will this fail?"
- Market risks, competitive threats
- Hidden costs, execution challenges
- Worst-case scenarios

**Agent 4: Customer Voice**
- "Would I pay for this?"
- Problem validation, willingness to pay
- User journey mapping, friction points
- Existing alternatives and switching costs

**Agent 5: Analyst**
- "What do the numbers say?"
- Market size (TAM/SAM/SOM)
- Revenue model viability
- Unit economics estimation
- Comparable benchmarks

**Step 3: Synthesize**
- Identify convergent ideas (multiple perspectives agree)
- Highlight key tensions and trade-offs
- Rank ideas by: impact × feasibility
- Select top 3 actionable ideas

**Step 4: Save to Obsidian**

**File:** `WizardingCode/Strategy/Brainstorms/<YYYY-MM-DD> <topic>.md`
```markdown
---
type: brainstorm
department: strategy
title: "<topic> — Brainstorm"
date_created: <YYYY-MM-DD>
tags:
  - "brainstorm"
  - "strategy"
  - "<topic-kebab-case>"
---

# <topic> — Brainstorm Session

## Question
[The framed question being explored]

## Perspectives

### Visionary
[Agent 1 output]

### Pragmatist
[Agent 2 output]

### Devil's Advocate
[Agent 3 output]

### Customer Voice
[Agent 4 output]

### Analyst
[Agent 5 output]

## Synthesis

### Convergent Insights
1. [Insight multiple perspectives agree on]

### Key Tensions
1. [Tension between perspectives]

### Top 3 Ideas (Impact × Feasibility)
1. **[Idea]** — [why it ranked #1]
2. **[Idea]** — [why it ranked #2]
3. **[Idea]** — [why it ranked #3]

### Recommended Next Steps
1. [Immediate action]
2. [Validation step]
3. [Decision deadline]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 5: Report**
```
═══ ARKA STRAT — Brainstorm Complete ═══
Topic:       <topic>
Perspectives: 5 (Visionary, Pragmatist, Devil's Advocate, Customer, Analyst)
Top idea:    <#1 ranked idea>
Obsidian:    WizardingCode/Strategy/Brainstorms/<date> <topic>.md
═════════════════════════════════════════
```

### /strat market <sector>

**Step 1: Research**
- Use WebFetch to gather market data on the sector
- Search for recent reports, trends, and key players
- Identify market structure and dynamics

**Step 2: Size the Market**
- TAM (Total Addressable Market) — total revenue opportunity
- SAM (Serviceable Addressable Market) — segment we can reach
- SOM (Serviceable Obtainable Market) — realistic capture

**Step 3: Analyze Trends**
- Growth drivers and headwinds
- Technology disruptions
- Regulatory changes
- Consumer behavior shifts

**Step 4: Map Opportunities**
- Underserved segments
- Entry barriers and moats
- Partnership possibilities
- Timing considerations

**Step 5: Save to Obsidian**

**File:** `WizardingCode/Strategy/Market/<YYYY-MM-DD> <sector>.md`
```markdown
---
type: market-analysis
department: strategy
title: "<sector> — Market Analysis"
date_created: <YYYY-MM-DD>
tags:
  - "market-analysis"
  - "strategy"
  - "<sector-kebab-case>"
---

# <sector> — Market Analysis

## Market Size
| Metric | Value | Source |
|--------|-------|--------|
| TAM | €X | [source] |
| SAM | €X | [source] |
| SOM | €X | [estimate] |
| Growth rate | X% CAGR | [source] |

## Key Players
| Company | Position | Strength | Weakness |
|---------|----------|----------|----------|
| [name] | [market share] | [strength] | [weakness] |

## Trends
1. **[Trend]** — [impact on market]
2. **[Trend]** — [impact on market]

## Opportunities
1. **[Opportunity]** — [why now, barrier to entry, potential size]

## Risks
1. **[Risk]** — [probability, impact, mitigation]

## Recommendation
[Clear strategic recommendation with reasoning]

---
*Part of the [[WizardingCode MOC]]*
```

### /strat competitor <url>

**Step 1: Gather Intelligence**
- Use WebFetch to analyze the competitor's website
- Product/service offering
- Pricing (if visible)
- Positioning and messaging
- Technology stack clues

**Step 2: SWOT Analysis**
- Strengths, Weaknesses, Opportunities, Threats relative to WizardingCode

**Step 3: Positioning Map**
- Map competitor on 2 key dimensions (e.g., price vs. quality, specialization vs. breadth)
- Identify our positioning gap or advantage

**Step 4: Save to Obsidian**

**File:** `WizardingCode/Strategy/Competitors/<YYYY-MM-DD> <name>.md`
```markdown
---
type: competitor-analysis
department: strategy
title: "<name> — Competitor Analysis"
url: "<url>"
date_created: <YYYY-MM-DD>
tags:
  - "competitor"
  - "strategy"
---

# <name> — Competitor Analysis

## Overview
- **URL:** <url>
- **Products/Services:** [list]
- **Positioning:** [how they position themselves]
- **Target audience:** [who they serve]

## SWOT
| Strengths | Weaknesses |
|-----------|-----------|
| [strength] | [weakness] |

| Opportunities | Threats |
|--------------|---------|
| [opportunity] | [threat] |

## Pricing
[Pricing structure and comparison]

## Positioning Map
[Where they sit vs. us on key dimensions]

## Key Takeaways
1. [What we can learn from them]
2. [Where we have an advantage]
3. [What to watch out for]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 5: Report**
```
═══ ARKA STRAT — Competitor Analysis ═══
Competitor:  <name>
URL:         <url>
Position:    [brief positioning summary]
Our edge:    [key advantage]
Obsidian:    WizardingCode/Strategy/Competitors/<date> <name>.md
═════════════════════════════════════════
```

---
*All output: `WizardingCode/Strategy/` — Part of the [[WizardingCode MOC]]*
