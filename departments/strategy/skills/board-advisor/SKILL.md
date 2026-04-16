---
name: strategy/board-advisor
description: >
  Board meeting preparation, deck structure, stakeholder management,
  and structured multi-perspective executive deliberation.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

# Board Advisor — `/strat board-advisor`

> **Agent:** Tomas (Strategy Lead) | **Framework:** Board Governance, Strategic Planning, 6-Phase Protocol

## Board Meeting Protocol (6 Phases)

| Phase | Action | Gate |
|-------|--------|------|
| 1. Context | Load company context + prior decisions | Founder confirms agenda |
| 2. Contributions | Independent perspectives (no cross-pollination) | Each role self-verifies |
| 3. Critic | Adversarial review of all contributions | Flag groupthink + gaps |
| 4. Synthesis | Merge perspectives into decision brief | Structured output |
| 5. Review | Founder approves / modifies / rejects | Human-in-the-loop |
| 6. Extraction | Log decisions + action items | Decisions persisted |

## Role Activation by Topic

| Topic | Activate |
|-------|----------|
| Market expansion | CEO, CMO, CFO, CRO, COO |
| Product direction | CEO, CPO, CTO, CMO |
| Hiring / org design | CEO, CHRO, CFO, COO |
| Pricing strategy | CMO, CFO, CRO, CPO |
| Technology decisions | CTO, CPO, CFO, CISO |

## Contribution Format (Per Role)

```
## [ROLE] -- [DATE]

Key points (max 5):
- [Finding] -- VERIFIED/ASSUMED
- [Finding] -- VERIFIED/ASSUMED

Recommendation: [clear position]
Confidence: High / Medium / Low
Source: [data origin]
What would change my mind: [specific condition]
```

## Board Deck Structure

| Section | Content | Slides |
|---------|---------|--------|
| Executive Summary | Decision required + recommendation | 1 |
| Context | Market data, company metrics, prior decisions | 2-3 |
| Options Analysis | Each option with TCO, risk, timeline | 2-4 |
| Perspectives | Key stakeholder views (for/against) | 1-2 |
| Recommendation | Chosen path + rationale + action items | 1 |
| Appendix | Supporting data, models, research | As needed |

## Failure Mode Quick Reference

| Failure | Fix |
|---------|-----|
| Groupthink (all agree) | Force "strongest argument against" from each role |
| Analysis paralysis | Cap at 5 points; force recommendation even with low confidence |
| Bikeshedding | Log as async action; return to main agenda |
| Role bleed | Critic flags; exclude from synthesis |
| Missing perspective | Identify who is not in the room (customer? ops?) |

## Critic Checklist

- [ ] Where did roles agree too easily? (suspicious consensus)
- [ ] What assumptions are shared but unvalidated?
- [ ] Who is missing from the room?
- [ ] What risk has nobody mentioned?
- [ ] Which role operated outside their domain?

## Stakeholder Management

| Stakeholder | Needs | Communication |
|-------------|-------|---------------|
| Investors | ROI, growth metrics, risk mitigation | Quarterly deck + metrics |
| Board members | Strategic direction, governance | Board pack 5 days before |
| Exec team | Clear decisions, ownership | Decision brief same day |
| Team leads | Action items, timelines | Cascade within 48 hours |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Board meeting without agenda → flag unproductive session risk
- No financial update section → flag governance gap
- Strategic pivot without board alignment → flag trust erosion

## Output

```markdown
## Board Decision Brief: <Topic>
### Decision Required: [one sentence]
### Perspectives: | Role | Position | Confidence | ... |
### Recommended Decision: [action + rationale]
### Action Items: | # | Action | Owner | Deadline |
```

## Obsidian Output

`WizardingCode/Strategy/Board/DECISION-<topic>-<date>.md`
