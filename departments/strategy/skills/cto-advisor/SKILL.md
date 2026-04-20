---
name: strategy/cto-advisor
description: >
  CTO-level advisory on tech strategy, build-vs-buy decisions, platform architecture,
  engineering team scaling, and technical debt management with DORA metrics.
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

# CTO Advisor — `/strat cto-advisor`

> **Agent:** Tomas (Strategy Lead) | **Framework:** Wardley Maps, DORA Metrics, ADR Governance

## Technology Strategy Assessment

| Dimension | Key Questions | Output |
|-----------|--------------|--------|
| Vision (3yr) | Where is the platform going? What bets are we making? | Technology roadmap |
| Architecture | What to build, refactor, or replace? | ADR with options + TCO |
| Innovation | 10-20% capacity for experimentation? | Innovation budget proposal |
| Build vs Buy | Core IP or commodity? | Scored decision matrix |
| Tech Debt | Managed or growing? Ratio < 25%? | Debt inventory + remediation plan |

## DORA Metrics Dashboard

| Metric | Elite | High | Medium | Low |
|--------|-------|------|--------|-----|
| Deploy frequency | On demand | 1/day-1/wk | 1/wk-1/mo | < 1/mo |
| Lead time | < 1 hour | 1 day-1 wk | 1 wk-1 mo | > 1 mo |
| Change failure rate | < 5% | 5-10% | 10-15% | > 15% |
| MTTR | < 1 hour | < 1 day | < 1 wk | > 1 wk |
| Tech debt ratio | < 15% | < 25% | < 35% | > 35% |

## Build vs Buy Decision Matrix

| Criterion | Weight | Scoring Guide |
|-----------|--------|--------------|
| Core IP relevance | 30% | 9 = core differentiator, 1 = commodity |
| 3-year TCO | 25% | Include: license + integration + maintenance + migration |
| Migration risk | 20% | How hard to switch away? Vendor lock-in? |
| Vendor stability | 15% | Revenue, funding, market position, bus factor |
| Integration effort | 10% | Days to production with existing stack |

**Default rule:** Buy unless it is core IP or no vendor meets >= 70% of requirements.

## ADR Template

```
Title: [Short noun phrase]
Status: Proposed | Accepted | Superseded
Context: [Problem + constraints]
Options:
  - Option A: [description] -- TCO: $X | Risk: Low/Med/High
  - Option B: [description] -- TCO: $X | Risk: Low/Med/High
Decision: [Chosen option + rationale]
Consequences: [What becomes easier? What becomes harder?]
```

## ADR Validation Checklist

- [ ] All options include 3-year TCO estimate
- [ ] At least one "do nothing" or "buy" alternative documented
- [ ] Affected team leads reviewed and signed off
- [ ] Consequences section addresses reversibility and migration path
- [ ] ADR committed to repository (not in Slack or docs)

## Engineering Team Scaling

| Team Size | Structure | Manager:IC Ratio | Senior:Junior |
|-----------|-----------|------------------|---------------|
| 1-8 | Single team, tech lead | N/A | 1:1 |
| 8-25 | 2-3 squads, eng manager | 1:5-8 | 1:2 |
| 25-75 | Departments, directors | 1:6-8 | 1:2-3 |
| 75+ | Org rewrite every 3x | 1:6-8 | 1:2-3 |

## Red Flags

- [ ] Tech debt ratio > 30% and growing
- [ ] Deploy frequency declining 4+ weeks
- [ ] No ADRs for last 3 major decisions
- [ ] Build times exceed 10 minutes
- [ ] Single points of failure on critical systems
- [ ] CTO is the only person who can deploy to production

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Build decision without ADR → flag reversibility risk
- Team doubling without architecture review → flag scaling debt
- No DORA metrics tracking → flag invisible engineering health

## Output

```markdown
## CTO Advisory: <Topic>

### Current State
| Metric | Value | Target | Status |
|--------|-------|--------|--------|

### Recommendation
[Decision + rationale grounded in data]

### Action Items
| # | Action | Owner | Deadline |
|---|--------|-------|----------|

### Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
```

## Output -> Obsidian: `WizardingCode/Strategy/CTO/ADVISORY-<topic>-<date>.md`

## References

- [build-vs-buy-framework.md](references/build-vs-buy-framework.md) — Evaluation criteria, TCO calculation template, risk matrix, vendor assessment checklist, and decision tree
