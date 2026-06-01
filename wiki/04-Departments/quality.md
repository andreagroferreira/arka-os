# Quality Gate

← [Departments index](README.md) · [Home](../Home.md)

> **Lead:** Marta (CQO, Tier 0) · **Agents:** 3 · Runs automatically on every workflow

The Quality Gate is not a department you invoke — it is a mandatory review layer that fires automatically at phase 11 of every non-trivial workflow. Marta (CQO) orchestrates two specialist directors: Eduardo reviews copy, language, tone, and AI pattern detection; Francisca reviews code quality, test coverage, and UX heuristics. All three agents operate at Tier 0 and carry absolute veto authority. A workflow cannot reach the user until the Quality Gate returns a binary APPROVED or REJECTED verdict.

This three-agent structure reflects a deliberate separation of concerns: language quality and technical quality require different expertise, and the same work must pass both lenses independently before it is considered done. The gate is the last line of defence against regressions, off-brand copy, accessibility failures, and SOLID violations shipping to production.

## The squad

| Agent | Role | Tier |
|---|---|---|
| Marta | Chief Quality Officer | 0 |
| Eduardo | Copy & Language Director | 0 |
| Francisca | Technical & UX Quality Director | 0 |

## Frameworks

**Marta — orchestration and quality standards**
- Jidoka (Toyota Production System) — stop the line the moment a defect is detected; do not pass bad work downstream
- Shift-Left Quality — catching defects earlier is categorically cheaper than catching them in review or production
- Zero Defect Mindset — quality is designed in, not inspected in at the end
- Deming's PDCA — Plan, Do, Check, Act; continuous improvement over blame
- Root Cause Analysis (5 Whys) — defects trigger structured root cause investigation, not patches
- Blameless postmortem — after an incident, the system failed before the person did

**Eduardo — copy and language review**
- Human Writing Standard — actively removes AI patterns, filler phrases, and passive constructions
- Audience Awareness (Schwartz 5 Levels) — copy must match the reader's awareness state
- StoryBrand Clarity (Miller) — the customer is the hero; every sentence must earn its place
- Tone consistency and cultural sensitivity across EN, PT-PT, PT-BR, ES, and FR

**Francisca — technical and UX review**
- SOLID Compliance Check — every class and function is validated against all five principles
- OWASP Top 10 Audit — security review is part of every code output, not a separate step
- Nielsen 10 Heuristics — UX outputs are reviewed against the full heuristic set
- Performance Budget — page weight, Core Web Vitals, and load time are checked against defined thresholds
- WCAG 2.2 AA accessibility review
- Test Pyramid Validation — coverage, test type distribution, and mutation testing are assessed

## How it runs

The Quality Gate triggers automatically in phase 11 of the [13-Phase Flow](../03-The-13-Phase-Flow.md). After each TODO item is completed and the per-item QA check passes, Marta orchestrates a parallel review:

1. Eduardo receives all written output — copy, documentation, user-facing strings, notifications.
2. Francisca receives all technical output — code, architecture decisions, UX flows, component designs.
3. Marta collates both verdicts and issues the gate decision.

If either Eduardo or Francisca returns REJECTED, the gate is REJECTED. The workflow loops back to fix the flagged items before the gate re-runs. There is no bypass, no partial approval, and no convenience exception — not even for low-stakes changes. The gate's consistency is the source of its value.

The gate runs on every workflow regardless of task type, department, or urgency. See [Quality Gate](../10-Quality-Gate.md) for the full specification including verdict format, rejection flow, and the constitutional rule (`mandatory-qa`) that makes it non-negotiable.

## When it matters most

The Quality Gate matters on every output, but it is most critical when:
- Code touches authentication, payments, or data access (OWASP + SOLID review is load-bearing)
- Copy goes to a public-facing surface where AI patterns or off-brand tone would damage trust
- A UX flow ships to users for the first time (Nielsen heuristics catch what usability testing would catch too late)
- A dependency or third-party integration is added (supply chain security check)

Related: [Quality Gate](../10-Quality-Gate.md) · [Core Concepts](../02-Core-Concepts.md) · [The 13-Phase Flow](../03-The-13-Phase-Flow.md)
