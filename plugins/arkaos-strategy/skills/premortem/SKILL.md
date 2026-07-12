---
name: premortem
description: >
  Decision-quality ritual for irreversible bets, owned by the Governance
  squad: premortem before (assume failure, cluster causes, rank
  likelihood x impact, add mitigations or kill-criteria) and blameless
  postmortem after (timeline, 5 Whys to a system cause, lessons with
  owners). TRIGGER: "premortem", "pré-mortem", "e se esta aposta falhar",
  "one-way door decision", "blameless postmortem", "aprender do falhanço
  sem culpas", "/strat premortem". SKIP: maintaining a standing project
  risk log -> pm/risk-register (continuous register, not a one-off
  ritual); production outage postmortems -> dev/incident.
---

# Premortem & Blameless Postmortem

> **Agent:** Guilherme (Decision Quality & Strategic Foresight) · escalates to the Governance squad (Afonso)
> **Framework:** Premortem (Klein) + Blameless Postmortem · KB: [[2026-05-30 G4 Pass - Cluster Estrategia e Decisao HBR]]

Use **before** any irreversible or high-stakes bet (a "two-way door" is reversible — skip it; a "one-way door" needs this).

## Premortem (before the decision)
1. **State the bet** in one sentence + the decider (RACI) + the deadline.
2. **Assume it failed.** "It's 6 months from now and this was a disaster. Why?"
3. Each participant writes failure causes independently (avoids groupthink/HiPPO).
4. Cluster the causes; rank by likelihood × impact.
5. For the top causes: add a mitigation or a kill-criterion. If a cause is fatal and unmitigable → **don't take the bet**.
6. Record: 3+ alternatives considered, the trade-off ("we do A, NOT B"), the decider, the review date.

## Blameless Postmortem (after the outcome)
1. **Timeline of what happened** — facts, not blame. Systems fail, not people.
2. What did we predict in the premortem that came true / didn't?
3. **Root cause** (5 Whys) — stop at a system/process, never at a person.
4. Lessons → concrete changes (a guardrail, a check, a default). Assign an owner.
5. Cheap failure is learning: Coca-Cola, Netflix and Amazon institutionalise this.

## Output
A decision record (premortem) + a postmortem note in Obsidian, linked to the bet. Feeds the org's learning loop.
