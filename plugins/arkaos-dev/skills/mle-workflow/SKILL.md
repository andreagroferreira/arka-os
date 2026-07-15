---
name: mle-workflow
description: >
  Turns model work into a production ML system — data contracts,
  reproducible training, measurable eval gates, a deployable artifact,
  and monitoring with a rollback path — using only the lanes the system
  needs. TRIGGER: "/dev mle-workflow", "productionise this model", "ML
  pipeline", "ranking/recommender/classifier/forecasting system", "model
  refresh", "pôr o modelo em produção", "notebook para pipeline", "eval
  gate do modelo". SKIP: RAG retrieval/context design -> dev/rag-architect
  wins; the app/API around the model with no ML lifecycle concern ->
  dev/architecture-design wins; prompt-injection/model-abuse threats ->
  dev/ai-security wins.
metadata:
  origin: arkaos
---

# ML Engineering Workflow

> **Agent:** Salvador (AI Engineering Specialist) | **Framework:** Data contracts, reproducible training, eval-gated promotion, monitored rollout

A model in a notebook is a result; a model in production is a system that
has to keep being right as the data underneath it moves. The gap between
the two is not the algorithm — it is the plumbing that makes a prediction
reproducible, gated on measured quality, deployable as an artifact, and
observable once real traffic arrives. This workflow builds that plumbing,
using only the lanes the system in front of you actually needs.

## Scope calibration first

Not every model has labels, online serving, a feature store, GPUs, or A/B
tests. Pick the lanes that fit and make the missing ones explicit
assumptions. A change that a data contract, a baseline, an eval script,
and a rollback note would make reviewable does not need a feature store.

## Lanes

### 1. Data contract
- Define the input schema, types, and allowed ranges; version it. A model is only as trustworthy as the guarantee on what reaches it.
- Name the label source and its latency (is the outcome known now, or in 30 days?). Undelayed evaluation of a delayed-label problem is a lie.
- Guard against **leakage**: a feature that encodes the target, or is computed with information unavailable at prediction time.

### 2. Reproducible training
- Pin the data snapshot, code version, dependency lockfile/environment, seed, and hyperparameters — a training run nobody can reproduce is not evidence.
- Separate train/validation/test by the axis that matches production (time-based split for anything time-ordered, not random).
- Emit a single versioned artifact (weights + preprocessing + the input schema it expects).

### 3. Eval gate (promotion criteria)
- State the metric and the threshold BEFORE training, tied to the decision the model drives — not accuracy for its own sake.
- Evaluate on **slices**, not just the aggregate: a model that is 95% overall and 40% on the segment that matters is a failure.
- Offline gate to promote; where traffic exists, an online check (shadow or canary) before full rollout.

### 4. Deployable artifact & serving
- The serving path must run the **same** preprocessing as training — train/serve skew is the most common silent production failure.
- Batch vs online: choose by the freshness the decision needs, not by default.
- Idempotent, versioned, with a health check.

### 5. Monitoring & rollback
- Watch input drift, prediction distribution, and — when labels arrive — realised quality against the offline estimate.
- A **rollback path** to the previous artifact that can be triggered without a retrain.
- Preserve every production failure (bad feature, stale label, artifact mismatch, drift) as a regression case.

## Process

1. Map the change onto the five lanes; mark which apply and which are explicit assumptions.
2. Find the existing training/feature/serving/eval paths before adding a parallel ML stack (`git grep`, read them).
3. Build the data contract and the eval gate first — they define what "done" means before any model work.

## Proactive Triggers

Surface these WITHOUT being asked:

- a feature computed from data unavailable at prediction time → the leakage, and the realistic offline score once it is removed
- a random train/test split on time-ordered data → the optimistic metric it produces and the time-based split that fixes it
- preprocessing written twice (once in training, once in serving) → the train/serve skew waiting to happen; share the code path

## Output

```markdown
## ML Engineering Plan

**System:** {what the model decides} · **Lanes in scope:** {of the five}
**Explicit assumptions:** {labels / serving / traffic / monitoring owner}

### Data contract
{schema, label source + latency, leakage checks}

### Training & eval gate
{reproducibility pins, split axis, metric + threshold + slices}

### Serving & monitoring
{batch/online, skew guard, drift signals, rollback trigger}

### Risks
- {the failure mode} → {the guard}
```
