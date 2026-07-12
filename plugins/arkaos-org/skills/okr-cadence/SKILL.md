---
name: okr-cadence
description: >
  Runs the OKR operating cadence (Doerr CFRs): quarterly set-score-reflect
  cycle, weekly check-ins, public 0.0-1.0 scoring with 70% as success, never
  tied to compensation, every KR owned. TRIGGER: "cadência de OKRs", "check-in
  semanal de OKRs", "score the OKRs", "OKR review", "CFR", "/org okr-cadence".
  SKIP: writing or cascading the OKRs themselves -> lead/okr-define (defines
  the goals; this skill runs them); pay and reward questions ->
  org/compensation-plan (OKRs must never drive comp).
---

# OKR Cadence

> **Agent:** Matilde (Alignment & OKR Steward) · escalates to Afonso (Chief of Staff)
> **Framework:** OKRs + CFRs (Doerr) · KB: [[2026-05-30 G4 Pass - Avalie o que Importa (OKRs Doerr)]] · [[Measure What Matters - OKRs]]
> Use `/lead okr-define` to *write* OKRs; this skill *runs the cadence*.

## Quarterly cycle
1. **Set** (start of quarter) — top-down direction + bottom-up proposals; align cross-dept; every KR has a named owner.
2. **Weekly check-in (CFR)** — Conversations, Feedback, Recognition. Update KR confidence; surface blockers early.
3. **Score** (end of quarter) — honest 0.0-1.0 per KR. **70% = success** (stretch is working); consistent 100% means goals are too easy; consistent <40% means too hard or wrong.
4. **Reflect** — keep / drop / rewrite for next quarter.

## The 3 questions ("Avalie o que importa")
- Are we advancing on what actually matters?
- Is the process healthy?
- Are we learning?

## Non-negotiables (anti-patterns)
- **Never tie OKRs to compensation** (kills honesty and stretch).
- **Every metric has an owner** (anti-Goodhart; no orphan metrics).
- **Separate OKRs from KPIs** — OKRs = change; KPIs = run-the-business health.
- KRs are **outcomes**, not tasks.

## Output
A live OKR scoreboard (per team, 0.0-1.0) + weekly CFR log in Obsidian. Drives the People & Org and Governance squads' alignment.
