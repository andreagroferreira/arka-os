---
name: ecom/cro-optimize
description: >
  Conversion Rate Optimization using CXL's ResearchXL framework.
  6-phase research process before testing anything.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
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

# CRO Optimization — `/ecom cro <page>`

> **Agent:** Alice (CRO Specialist) | **Framework:** ResearchXL (Peep Laja / CXL)

## ResearchXL: 6 Phases of Research BEFORE Testing

### 1. Heuristic Analysis
- Relevance: Is the page relevant to the visitor?
- Clarity: Is the value proposition clear in 5 seconds?
- Friction: What causes hesitation?
- Distraction: What takes attention from the goal?

### 2. Technical Analysis
- Core Web Vitals (LCP, INP, CLS)
- Cross-browser/device testing
- JavaScript errors, broken elements

### 3. Analytics Analysis
- Funnel drop-off points
- High bounce-rate pages
- Conversion by traffic source, device, segment

### 4. Heatmaps & Session Recordings
- Click heatmaps: where do users click?
- Scroll maps: how far do they scroll?
- Session recordings: how do they actually navigate?

### 5. Qualitative Surveys
- Exit surveys: "Why are you leaving without buying?"
- On-page: "Did you find what you were looking for?"
- Customer interviews

### 6. User Testing
- 5 users = 85% of problems found
- Task-based: "Find and buy product X"
- Think-aloud protocol

## Test Prioritization (PIE/ICE)

| Test | Potential | Importance | Ease | Score |
|------|-----------|-----------|------|-------|
| ... | 1-10 | 1-10 | 1-10 | P*I*E |

## Rules
- 95% statistical significance minimum
- Run for 2+ complete business cycles
- Test ONE variable at a time
- Document hypothesis, variant, result, learning

## Output → Research findings + prioritized test backlog + hypothesis for top 3 tests
