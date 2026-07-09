---
name: arka-quality
description: >
  Quality Gate department. Cross-department quality supervision with absolute veto power.
  Reviews ALL output from ALL departments before delivery. Nothing ships without APPROVED.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Quality Gate — ArkaOS v2

> **CQO:** Marta (Tier 0, veto) | **Agents:** 3 | **Topology:** Enabling (cross-cutting)

## How It Works

The Quality Gate is NOT invoked by the user directly. It runs automatically as the
second-to-last phase of EVERY workflow in EVERY department.

The gate is EVIDENCE INTERPRETATION, not persona role-play. The verdict DERIVES
from executable check output; reviewers interpret the report, they never
override it with narrative.

```
Any Department Workflow:
  ...
  Phase N-1: QUALITY GATE
    0. Output-judge (constitution gate-judges, MEDIUM/HIGH work only):
       one judge dispatched via the Agent tool with
       JUDGE_VERDICT_JSON_SCHEMA (core.governance.judge), frontier
       model, over deliverable + diff + evidence report. REVISE loops
       the work back before the personas run (max 2); PASS findings
       become reviewer input. Record it:
       arka-py -m core.evals.record_cli --kind judge
    1. Run the evidence engine over the project/diff:
         ~/.arkaos/bin/arka-py -m core.governance.evidence_checks <project_dir> \
           [--changed-files f1,f2] [--test-command '...'] --json
    2. Marta dispatches Eduardo + Francisca to INTERPRET the report:
       - Eduardo: spellcheck section + prose review of changed copy
       - Francisca: lint / typecheck / tests / coverage / security-grep
    3. Verdict rules (binary, evidence-floored):
       - overall == "fail"  → REJECTED. Always. No persona can override
         failing evidence with narrative.
       - overall == "pass"  → APPROVED only if reviewers find no blocker
         the checks cannot see (logic, copy, UX).
       - overall == "insufficient-evidence" → APPROVED only with an
         explicit justification in the verdict notes; otherwise REJECTED.
    4. If ANY reviewer rejects → work loops back with the blockers list
    5. If ALL approve → Marta issues final APPROVED verdict
    6. Record the label (evals ADR 2026-07-09): pipe Marta's final
       QGVerdict JSON to
       `arka-py -m core.evals.record_cli --department <dept>
        [--deliverable <title>] [--eval-task-id <id>] [--session-id <id>]`
       — every verdict feeds the eval/distillation corpus
       (~/.arkaos/telemetry/qg-verdicts.jsonl). Applies to EVERY review,
       not only eval runs; --eval-task-id only when the review judged a
       config/evals task.
    7. Recipe promotion (Interaction Reform PR7, APPROVED reusable
       features only): when the deliverable is a feature worth reusing
       across projects (auth flow, payment integration, a standard UI
       pattern…), PROPOSE to the operator "promote this to a recipe?".
       On confirmation, capture it —
       `arka-py -m core.knowledge.recipes_cli capture --spec <spec.json>`
       (spec = {recipe, narrative, files}). Capture is fail-closed:
       every field and file is sanitized first, refused without a
       redaction config. Never silent — always operator-confirmed.
  Phase N: DELIVERY
    → Only reaches user after APPROVED from all three
```

## Reviewer Dispatch Contract

Reviewers are dispatched via the Agent tool with STRUCTURED OUTPUT. The output
schema is `QG_VERDICT_JSON_SCHEMA` from `core.governance.qg_verdict` (the JSON
Schema of the `QGVerdict` pydantic model):

    from core.governance.qg_verdict import QG_VERDICT_JSON_SCHEMA

    Agent(
        subagent_type="francisca-tech",       # .claude/agents/francisca-tech.md
        model="sonnet",                        # opus ONLY for Tier 0/security scope
        prompt="<evidence report JSON> + <diff summary> — interpret and return QGVerdict",
        output_schema=QG_VERDICT_JSON_SCHEMA,  # structured-output param
    )

Each reviewer MUST return a `QGVerdict` JSON object: `verdict`
(APPROVED|REJECTED), `evidence_report` (embedded summary), `blockers`
(`[{check, detail, file}]`), `reviewer`, `model_used`, `notes`. The pydantic
model rejects APPROVED-with-failing-evidence at validation time, and
`core.governance.review_workflow` raises `ValueError` on any attempt to record
an approval over `evidence_overall == "fail"`.

## Squad

| Agent | Role | Tier | DISC | Scope |
|-------|------|------|------|-------|
| **Marta** | CQO — Orchestrates, aggregates, final verdict | 0 | C+D | Everything |
| **Eduardo** | Copy Director — Text quality | 0 | C+S | Spelling, grammar, tone, AI patterns, accentuation |
| **Francisca** | Tech Director — Technical quality | 0 | D+C | Code, tests, UX, data, security, performance |

## Eduardo Reviews (Text)

- Spelling and grammar (EN, PT-PT, PT-BR, ES, FR)
- Accentuation correctness in all languages
- Tone and voice consistency with brand
- AI pattern detection (no "leverage", "utilize", "robust", "streamline")
- Factual accuracy in claims and data
- Human writing standard compliance

## Francisca Reviews (Technical)

- SOLID principles compliance
- Test coverage and quality (>= 80%)
- Clean Code standards (naming, functions, nesting)
- Security (OWASP Top 10 check)
- Performance (Core Web Vitals, API latency)
- UX/UI (Nielsen Heuristics, accessibility WCAG AA)
- Data integrity and API contract consistency
- Product data accuracy (pricing, descriptions, attributes)

## Verdicts

| Verdict | Meaning | Next Step |
|---------|---------|-----------|
| **APPROVED** | All reviewers approve | Proceed to delivery |
| **REJECTED** | One or more issues found | Loop back with specific issue list |

There is no "APPROVED WITH CAVEATS". It's binary. Fix issues first.

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate reviewers (Eduardo/Francisca) run on `sonnet` by DEFAULT.
  `opus` is used ONLY when the diff is Tier 0 scope (constitution, security,
  release pipeline, installer auth) or the deliverable is security-flagged.
- Marta keeps her veto regardless of the model tier the review ran on —
  the verdict derives from evidence, not from model size.
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
