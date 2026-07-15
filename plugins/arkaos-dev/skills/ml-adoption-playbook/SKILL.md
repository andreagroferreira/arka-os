---
name: ml-adoption-playbook
description: >
  Decides whether a problem needs ML at all, then adds it to a non-ML
  codebase the cheap way — heuristic baseline first, a defined metric and
  mistake budget, data readiness, and a decoupled seam before any model.
  TRIGGER: "/dev ml-adoption-playbook", "should we use ML for this", "add
  ML to", "is this an ML problem", "machine learning for X", "vale a pena
  ML aqui?", "adicionar ML ao projeto", "modelo ou regras?". SKIP: the
  model is already chosen and the job is to productionise it ->
  dev/mle-workflow wins; a ranking/feed pipeline's plumbing ->
  dev/rag-architect or dev/architecture-design wins.
metadata:
  origin: arkaos
---

# ML Adoption Playbook

> **Agent:** Salvador (AI Engineering Specialist) | **Framework:** Heuristic-first, metric-and-mistake-budget, incremental adoption

The most expensive way to add machine learning to a product is to reach
for a model before asking whether rules would do. A regex, a threshold,
or a lookup table ships in an afternoon, is trivial to debug, and is
often within a few points of what a model would give — and if it is not,
it becomes the baseline the model has to beat. This playbook decides
whether the problem is really an ML problem, and if it is, adds ML to a
codebase that has none of the scaffolding, one committed step at a time.

## Phase 1 — Framing & feasibility (before any model)

- **Heuristic check.** Could a rule, threshold, or lookup solve this
  acceptably? If yes, ship that first — it is the baseline and often the
  answer. A model that cannot beat a well-tuned heuristic is not worth
  its operational cost.
- **Metric.** Define how success is measured, tied to the product
  decision — before touching data. No metric, no project.
- **Mistake budget.** State what a wrong prediction costs and how many
  are tolerable. This sets the bar the model must clear and whether a
  human stays in the loop.
- **Data reality.** Do labelled examples exist, or a path to them? Is the
  outcome observable, and when? A problem with no labels and no path to
  them is not yet an ML problem.

## Phase 2 — Data readiness

- Locate the data that would feed the model; assess volume, quality, and
  bias before assuming it is usable.
- Confirm the label is available at the time a prediction is needed, not
  only in hindsight.

## Phase 3 — Architectural seam

- Add a decoupled boundary where the prediction plugs in — an interface
  the current heuristic satisfies too, so the model can replace the rule
  without rewiring the app.
- Keep the heuristic as the fallback and the regression baseline.

## Phase 4 — Baseline model

- Integrate the simplest model that could work behind the seam; compare
  it to the heuristic on the defined metric and mistake budget.
- Promote only if it clears the bar. If it does not, the heuristic stays
  and the finding is recorded — a negative result is still a result.

## Proactive Triggers

Surface these WITHOUT being asked:

- a request to "use ML" for something a threshold or lookup handles → propose the heuristic baseline first and the bar the model must beat
- an ML plan with no defined metric or mistake budget → stop; those come before data
- no labelled data and no path to it → this is not yet an ML problem; name what would make it one

## Output

```markdown
## ML Adoption Assessment

**Problem:** {what decision needs to be made}
**Heuristic baseline:** {the rule that ships today, and how close it gets}
**Verdict:** {ML justified? / heuristic suffices / not yet an ML problem}

### If ML is justified
- **Metric & bar:** {measure + threshold the model must beat the baseline by}
- **Mistake budget:** {cost of a wrong call + human-in-loop or not}
- **Data readiness:** {labels? volume? label latency?}
- **Seam:** {the interface where the model plugs in, heuristic as fallback}
```
