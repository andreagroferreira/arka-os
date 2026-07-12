---
name: okr-define
description: >
  Defines OKRs with John Doerr's framework, cascading company -> team:
  qualitative Objectives, quantitative Key Results, scoring criteria and
  check-in schedule. TRIGGER: "define OKRs", "objetivos do trimestre", "OKRs
  da equipa", "key results", "quarterly goals", "/lead okr <scope>". SKIP:
  running the quarterly/weekly ritual on OKRs that already exist ->
  org/okr-cadence (operates the cadence; this skill writes the OKRs);
  individual performance goals -> lead/performance-review (person-level, not
  team objectives).
---

# OKR Definition

> **Agent:** Rodrigo (Leadership Director) | **Framework:** OKRs (Doerr / Andy Grove)

## Formula

**"I will [OBJECTIVE] as measured by [KEY RESULTS]"**

## Rules

### Objectives (O)
- Qualitative, inspirational, ambitious
- 3-5 per period (quarterly)
- Answers: "What do we want to achieve?"
- Starts with action verb

### Key Results (KR)
- Quantitative, measurable, time-bound
- 2-5 per Objective
- Answers: "How do we know we achieved it?"
- Always a number (not a task)

## Scoring
- **0.0-0.3:** Failed (red)
- **0.4-0.6:** Progress but missed (yellow)
- **0.7-1.0:** Achieved (green)
- **Target:** 70% = stretch goals are working
- **100% consistently** = goals are too easy

## Cascading

```
COMPANY OKRs (CEO/Leadership)
    ↓ 40% top-down
DEPARTMENT OKRs (Squad Leads)
    ↓ 60% bottom-up
TEAM OKRs (Individual Contributors)
```

## Common Mistakes
- KRs that are tasks, not outcomes ("Launch feature X" → bad)
- Too many OKRs (max 5 Os with 5 KRs each = 25 things to track)
- Linking OKRs to compensation (kills ambition)
- Setting OKRs once and never checking (must have weekly check-ins)

## Example

```
OBJECTIVE: Become the #1 AI agent framework for developers
  KR1: 5,000 npm installs by end of Q2
  KR2: NPS > 60 in user survey (min 100 responses)
  KR3: 50+ community-contributed skills in marketplace
  KR4: Featured in 3+ developer publications
```

## Cadence
- **Quarterly:** Set and review company + team OKRs
- **Weekly:** 15-min check-in on KR progress
- **End of quarter:** Score + retrospective

## Output → OKR document with company + team levels, scoring criteria, check-in schedule
