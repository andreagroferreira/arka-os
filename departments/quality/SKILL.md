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
    1. Run the evidence engine over the project/diff — SCOPED
       (Gate Economy): derive the changed set from the merge base and
       pass --changed-files ALWAYS (activates scoped lint/typecheck,
       inert-diff skips, manifest-only verdict). Intermediate rounds
       pin --test-command to the tests covering the changed modules
       (tests/python/test_<module>.py naming; uncertain mapping →
       omit it, fallback is the FULL suite, never empty). The final
       pre-merge gate NEVER pins --test-command: full suite, exit 0.
       Drop design-slop,ui-screenshot via --checks when no UI file
       changed, and spellcheck when no .md/copy changed:
         ARKA_CALL_CATEGORY=subagent:quality \
         ~/.arkaos/bin/arka-py -m core.governance.evidence_checks <project_dir> \
           --changed-files f1,f2 [--test-command '...'] [--checks ...] --json
    2. Marta dispatches Eduardo + Francisca to INTERPRET the report:
       - Eduardo: spellcheck section + prose review of changed copy
       - Francisca: lint / typecheck / tests / coverage / security-grep
    3. Verdict rules (binary, evidence-floored, severity-weighted —
       Gate Economy, operator-approved 2026-08-09):
       - overall == "fail"  → REJECTED. Always. No persona can override
         failing evidence with narrative. (Minor-severity check
         failures — spellcheck, design-slop, ui-screenshot — no longer
         flip the overall: they surface as findings instead.)
       - overall == "pass"  → APPROVED only if reviewers find no
         GATING (blocker/major) finding the checks cannot see (logic,
         copy, UX). Minor findings fix forward in the same turn: apply
         the correction, verify it with a scoped re-run, record it in
         the aggregate notes, and approve. A REJECTED backed only by
         minors is rejected by the schema itself.
       - overall == "insufficient-evidence" → APPROVED only with an
         explicit justification in the verdict notes; otherwise REJECTED.
    4. If ANY reviewer rejects → work loops back with the blockers list.
       On the redo round, re-dispatch ONLY reviewers whose domain
       changed since their artifact; carry the rest via digest_carries
       (QGDigestCarry — reviewer, exact digest, >= 40-char reason,
       validated against the session ledger). Carry is the norm for an
       untouched domain, not the exception. HARD STOP at the redo cap:
       when ~/.arkaos/quality-gate/<session>/ESCALATE exists (dropped
       by the record CLI at REDO_CAP = 2), no further reviewer is
       dispatched and no new round opens — the full verdict history
       goes to the operator for a decision (excellence-mandate).
    4.5. Marta's gate-closing report reproduces each reviewer verdict
         VERBATIM under `### <Reviewer> — verbatim`, with the ledger
         artifact path (~/.arkaos/quality-gate/<session>/) beside it.
         Summarising a reviewer in the aggregator's words is relay,
         not report — a relay inside a gate is a point of distortion.
    5. If ALL approve → Marta issues final APPROVED verdict
    6. Record the label (evals ADR 2026-07-09): pipe Marta's final
       QGVerdict JSON to
       `arka-py -m core.evals.record_cli --kind qg --session-id <session>
        --department <dept> [--deliverable <title>] [--eval-task-id <id>]`
       (the aggregate path REQUIRES --session-id: the
       anti-self-approval guard reads that session's reviewer ledger
       and refuses an aggregate it cannot support)
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

Reviewers are dispatched via the Agent tool. The `QGVerdict` schema
(`QG_VERDICT_JSON_SCHEMA` from `core.governance.qg_verdict`) travels INSIDE
the prompt — the Agent tool has no structured-output parameter, so the
contract IS the dispatch prompt naming the exact fields (PR-B4 dispatch
shape; a dispatch that invents its own field names fail-softs the artifact):

    from core.governance.qg_verdict import QG_VERDICT_JSON_SCHEMA

    Agent(
        subagent_type="francisca-tech",  # .claude/agents/francisca-tech.md
        model="opus",                    # quality_gate.model_policy: best available
        prompt="<evidence report JSON incl. report_digest> + <diff summary> — "
               "interpret and return, in a ```arka-qgverdict fence, a QGVerdict "
               "with fields: verdict, evidence_report, blockers "
               "[{check, detail, file, severity, verdict}], reviewer, "
               "model_used, evidence_digest (= the report_digest), notes",
    )

Each reviewer MUST return a `QGVerdict` JSON object in a ```arka-qgverdict
fence: `verdict` (APPROVED|REJECTED), `evidence_report` (embedded summary),
`blockers` (`[{check, detail, file, severity, verdict}]` — `check` names the
evidence check; the aggregate guard's coverage matching keys on it;
`severity` is blocker|major|minor — findings gate by weight, minors fix
forward), `reviewer`,
`model_used`, `evidence_digest` (mandatory since PR-B4 — an artifact without
it cannot support an APPROVED aggregate), `notes`. The Pydantic model rejects
APPROVED-with-failing-evidence at validation time, and the anti-self-approval
guard (PR-B3, hardened PR-B4) refuses an APPROVED aggregate the session's
reviewer ledger cannot support — dispatch-shape issues are demoted to
warnings on a REJECTED one; fabrication vectors (quorum, a vanishing
CONFIRMED blocker) refuse regardless of verdict.

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
- Quality Gate agents (Marta aggregating, Eduardo + Francisca reviewing)
  run on the BEST model available — single source: constitution
  `quality_gate.model_policy` (Excellence Reform 2026-07-05, frontier
  tier; per-role overrides in `~/.arkaos/models.yaml`, Model Fabric).
  Economy tiers never review.
- Marta keeps her veto regardless of the model tier the review ran on —
  the verdict derives from evidence, not from model size.
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
