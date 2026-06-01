---
name: pm/discovery-plan
description: >
  Product discovery using Teresa Torres' Opportunity Solution Tree.
  Map outcomes to opportunities to solutions to experiments.
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

# Product Discovery — `/pm discover <opportunity>`

> **Agent:** Carolina (Product Manager) + Renata (UX Researcher) | **Framework:** Continuous Discovery (Teresa Torres) + Dual-Track (Cagan)
> KB: [[Habitos de Descoberta Continua - Teresa Torres]] · [[Inspirado - Marty Cagan]] · [[Personas/Teresa Torres]] · [[Personas/Marty Cagan]]
>
> Discovery is a **habit, not a phase**. Map every solution back to an opportunity back to the outcome — **no orphan features**. Ask about specific past behaviour, not hypotheticals (**behavior > self-report**) — pair with Renata's research methods.

## Opportunity Solution Tree

```
        DESIRED OUTCOME (business metric)
               |
      +--------+--------+
      |        |        |
 OPPORTUNITY  OPP      OPP    (customer needs/pains)
      |        |        |
   +--+--+  +--+--+  +--+--+
   |  |  |  |  |  |  |  |  |
  SOL SOL  SOL SOL  SOL SOL   (ideas that address opps)
   |  |     |  |     |  |
  EXP EXP  EXP EXP  EXP EXP   (tests to validate assumptions)
```

## Process

1. **Define outcome** — Which business metric are we trying to move?
2. **Map opportunities** — Customer needs/pains from interviews (not features)
3. **Generate solutions** — 2-3 solutions per opportunity (never evaluate just 1)
4. **Map assumptions** — For each solution, what must be true?
5. **Design experiments** — Test riskiest assumptions first (high risk + low evidence)

## Weekly Cadence
- 1 customer interview per week (minimum)
- Update OST weekly
- Prioritize experiments by: risk x evidence gap

## Assumption Types
- **Desirability:** Do customers want this?
- **Viability:** Can we sustain this business-wise?
- **Feasibility:** Can we build this?
- **Usability:** Can customers figure this out?

## Dual-Track (Cagan)
Run discovery for cycle N+1 **in parallel** with delivery shipping cycle N — never sequential phases. Teams get **problems to solve**, not features to build (the 4 product risks above must be tested before a solution is "ready").

## Output → OST diagram + assumption map + experiment backlog
