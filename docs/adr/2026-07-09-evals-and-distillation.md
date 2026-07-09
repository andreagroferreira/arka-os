# ADR: Eval harness foundation and the path to local-model distillation

- **Date:** 2026-07-09
- **Status:** Accepted
- **Context:** E2E audit v4.3.6, P2 findings "Evals" and "Treino"
- **Related:** `docs/adr/2026-07-04-evidence-flow.md`, `core/governance/qg_verdict.py`

## Context

The E2E audit left two P2 items open:

1. **Evals** — no reference task suite exists, so there is no objective
   way to measure whether an agent, prompt change, or model swap made a
   department better or worse. The audit noted that QG verdicts
   (APPROVED/REJECTED with blockers and evidence) are *free labels*
   being thrown away.
2. **Treino** — Claude models are not fine-tunable; the operator's
   improvement lever there is context engineering (skills, experiences,
   Synapse layers). Real fine-tuning only applies to the local Ollama
   models served through the Model Fabric gateway (execution tier), via
   LoRA distillation on sanitized transcripts.

## Decision

### 1. Eval tasks are repo-versioned YAML, judged by properties + QG

- Schema: `core/evals/schema.py::EvalTask` — id, department, prompt,
  `expected_properties` (verifiable), rubric, tags.
- Seed set: `config/evals/<department>.yaml`, 2 tasks × 5 core
  departments (dev, marketing, finance, strategy, kb). Locked by
  `tests/python/test_evals.py` (departments must exist, ids unique,
  ≥10 tasks).
- An eval RUN = dispatch the task prompt through the normal squad flow
  and judge the deliverable against `expected_properties` + rubric via
  the existing Quality Gate — evals reuse the QG, they do not build a
  second judging stack.

### 2. QG verdicts are persisted as labels from now on

`core/evals/verdict_labels.py::record_verdict_label` appends every
structured `QGVerdict` to `~/.arkaos/telemetry/qg-verdicts.jsonl`
(telemetry conventions: never raises, env override for tests). The
orchestrator calls it after each QG review, tagging deliverable,
department and (when applicable) `eval_task_id`. This makes every
review — including ordinary PR reviews — a labeled example.

### 3. Distillation is gated on the label corpus, not started now

LoRA fine-tuning of the local execution models (Ollama) starts only
when BOTH hold:

1. ≥500 labeled examples in `qg-verdicts.jsonl` (mixed
   APPROVED/REJECTED, multi-department), and
2. a sanitization pass exists that provably strips client identifiers
   from transcripts (confidentiality is NON-NEGOTIABLE — see
   `feedback_confidentiality`; the v2.18.0 npm leak is the cautionary
   precedent).

Claude-tier models are explicitly out of scope for fine-tuning; their
improvement loop remains experiences → skills → Synapse injection.

## Consequences

- Model Fabric changes (e.g. swapping the execution model) become
  measurable: run the seed set before/after, compare QG outcomes.
- The label corpus grows passively with normal work; no separate
  labeling effort.
- Follow-ups: an eval runner CLI (`arka-py -m core.evals.runner`) that
  automates dispatch + judging; wiring `record_verdict_label` into the
  QG skills' instructions; sanitization tooling as its own deliverable
  before any training run.
