---
name: org/culture-define
description: >
  Ships a production culture document: inversion-tested values, observable
  behaviour maps, load-bearing ritual catalogue, decision principles, and
  operationalisation into hiring, performance, and promotion (Netflix Culture,
  Lencioni, Dalio). TRIGGER: "define a cultura", "valores da empresa",
  "company values", "culture document", "decision principles", "/org culture".
  SKIP: checking whether stated values are actually lived ->
  lead/culture-audit (audits the existing culture; this skill defines it);
  trust or conflict dysfunction in one team -> lead/team-health.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Culture Define — `/org culture`

> **Lead:** Sofia (COO) | **Cross-dept:** Tomas (Strategy) + Clara (KB) + Eduardo (Copy) + Marta (CQO) | **Frameworks:** Netflix Culture + Lencioni Five Dysfunctions + Dalio Principles + Inversion Test

## What ships

A production culture document in 6 deliverables:

1. **Cultural archaeology** — what's already true vs aspirational
2. **Values set** — 4-6 values that pass the inversion test
3. **Behaviour map** — 3-5 observable behaviours per value
4. **Ritual catalogue** — value-reinforcing rituals with owners + frequency
5. **Decision principles** — how the org decides, disagrees, commits
6. **Operationalisation plan** — culture wired into hiring + onboarding + performance + promotion

## The Inversion Test (the only test that matters)

A value passes the inversion test if **its opposite is a defensible position held by another reputable company**. Values that fail the inversion test are platitudes, not values.

| Value | Inverse | Pass / Fail |
|---|---|---|
| "Move fast" | "Move with deliberation, premortem every change" | PASS — Boeing, surgical software vendors |
| "Customer obsession" | "Engineer obsession — make the system right, customers adapt" | PASS — Linux kernel, AWS internal services |
| "Excellence" | (no defensible opposite — nobody says "mediocrity") | FAIL — platitude |
| "Integrity" | (no defensible opposite — nobody says "dishonesty") | FAIL — platitude |
| "Bias for action" | "Bias for analysis — measure twice, cut once" | PASS — research orgs, regulated industries |
| "Radical candour" | "Diplomatic harmony — preserve relationships over signals" | PASS — Japanese corporate culture, diplomatic services |

If you cannot name a real company that holds the opposite position, the value is not a value. Drop it.

## Cultural Archaeology (extract before defining)

Before defining culture aspirationally, **map what already is**. Cultural artefacts to inspect:

- **Slack/Discord patterns** — who responds when, what gets celebrated, what gets ignored
- **Decision logs** — what got built vs what got rejected, with rationale
- **Founder choices** — first hires, first firings, first product cuts
- **Calendar reality** — what gets weekly time vs quarterly time vs never
- **Recognition patterns** — who gets praised publicly, for what
- **Conflict patterns** — how disagreement is surfaced, escalated, resolved

Map the as-is. Then compare to the desired-is. The gap between as-is and desired-is is the culture-change work — and most of it is operationalisation, not aspiration.

## Behaviour Mapping (observable + coachable)

Each value translates to 3-5 behaviours that are:

- **Observable** — a third-party could watch and identify the behaviour
- **Coachable** — a manager can give feedback specific to this behaviour
- **Inversion-defensible** — the inverse behaviour would identifiably belong to a different value

Example translation:

```yaml
value: "Radical Candour"
behaviours:
  - observable: "In meetings, names a disagreement explicitly within 30 seconds of forming it"
    coachable: "Manager can flag: 'You sat on that disagreement for 5 minutes before raising it. What kept you quiet?'"
  - observable: "Gives critical feedback to peers directly before going to manager"
    coachable: "Manager can flag: 'You came to me about Marco's work — have you told Marco first?'"
  - observable: "Writes the dissenting view in the decision document, not in DM"
    coachable: "Manager can flag: 'I see you DM'd me your concern — that belongs in the doc thread.'"
```

Behaviours that aren't observable + coachable are aspirations, not culture.

## Ritual Catalogue (load-bearing rituals)

Rituals reinforce values by repetition. Each ritual must:

- **Have an owner** — named human who runs it
- **Have a value it reinforces** — explicit link, not "team-building"
- **Be load-bearing** — if removed, the value erodes
- **Have a cadence** — daily / weekly / monthly / quarterly / annual

Decorative rituals (Friday afternoon trivia with no value link) should be cut. Load-bearing rituals (Monday decision-log review reinforcing "Radical Candour") should be defended.

Sample ritual catalogue format:

```yaml
rituals:
  - name: "Decision Log Review"
    cadence: weekly
    owner: <coo>
    value_reinforced: Radical Candour + Document Everything
    description: 30min weekly review of decisions made + dissents noted
    load_bearing: yes  # removing this means decisions lose dissent visibility
```

## Decision Principles

How the org decides:

```yaml
decision_principles:
  fast_lane:
    criteria: "Reversible, contained blast radius, single owner can decide"
    process: "DRI decides, posts decision in #decisions, moves on"
  slow_lane:
    criteria: "Irreversible, cross-team impact, or > $X spend"
    process: "RFC posted, 1-week comment period, decision meeting, exec sign-off if > $Y"
  disagree_and_commit:
    when: "Decision is made and you dissented"
    expected_behaviour: "Make the decision succeed as if it were yours"
  escalation:
    when: "Cannot reach decision within timebox"
    process: "Escalate to specific named human, no triangulation"
```

Decision principles must be specific enough to predict behaviour, not vague enough to mean nothing.

## Operationalisation (the hard part)

Values without operational integration are wall posters. Wire culture into:

### Hiring
- Interview rubrics test for each value's observable behaviours
- "Culture interview" measures inverse-test alignment, not generic "good fit"
- Reject criteria: candidate who consistently exhibits inverse behaviours

### Onboarding
- Day 1: Values + behaviour map + inversion test framing
- Week 2: Shadowing of load-bearing rituals
- Month 1: Reflection conversation — which values felt foreign vs native?

### Performance Review
- Behaviour-specific feedback against each value's observable list
- "What value did you most embody this period? What evidence?"
- Areas-for-development tied to specific behaviours

### Promotion
- Each level requires demonstrating specific behaviours
- Senior level requires modelling behaviours to others
- Lead level requires defending values when convenient to violate them

## Common Failure Modes

1. **Platitude values** — "Excellence", "Integrity", "Innovation" without inverses. Drop them
2. **As-is denial** — defining the aspirational culture without mapping the actual culture. Gap becomes invisible
3. **Decorative rituals** — Friday trivia with no value link. Cut it
4. **Behaviours without observability** — "be a team player" is not a behaviour, "names disagreement within 30 seconds" is
5. **Wall poster syndrome** — values defined but not wired into hiring / performance / promotion. Operationalisation is 80% of the work

## Output → Obsidian: `WizardingCode/Org/Culture/<company>-<date>/`

Delivers: cultural archaeology (as-is map) + values set (inversion-tested) + behaviour map (3-5 observable behaviours per value) + ritual catalogue (load-bearing only) + decision principles + operationalisation plan (hiring + onboarding + performance + promotion) + 1-page executive summary.
