<!--
ArkaOS canonical skill template (PR-3 of the prompt-surface plan,
2026-07-08 frontier audit). Reconstructed from the structure every
Anthropic bundled skill shares; adapted to ArkaOS conventions.

How to use: copy, fill, DELETE every <angle-bracket> placeholder and
this whole comment before committing. Sections marked [optional] are
deleted when they don't apply — an empty section is worse than none.

Authoring rules (enforced at review):
- The description is a TRIGGER/SKIP contract, not a summary of what the
  skill does. Put the exact words (pt-PT AND en) an operator would type.
- Every step is imperative. No "consider", no "you should".
- Every rule carries its reason in half a sentence.
- Anything computable goes to scripts/ ("run it; don't eyeball it").
- Anything that survives a handoff (subagent prompt, report line) is a
  verbatim block: "use this EXACT string — do not paraphrase".
- Output contracts are shown as a FILLED example, never described in
  the abstract.
- Only document commands you actually ran, in this repo, this session.
- Line test before commit: "would removing this line cause a mistake?"
  If no, cut it.
-->
---
name: <kebab-slug — must equal the directory name and slash command>
description: >
  <WHAT in one clause + WHEN in trigger words the user would type.>
  TRIGGER: <concrete observable signals — user words (pt-PT/en), file
  patterns, imports, commands. Include timing if it matters: "load
  BEFORE <action>; don't skip because it looks trivial".>
  SKIP: <counter-signals — when a neighbouring skill wins instead;
  name that skill so routing collisions resolve deterministically.>
---

# <Skill name>

<ONE sentence of persona ONLY if it calibrates judgment — "You are the
<role> reviewing X" — followed by the skill's central principle with its
reason. No backstory, no traits. Delete the persona line if the skill is
procedural.>

## Non-negotiables

<Invariants that hold in EVERY run of this skill, outside the procedure
flow. Bold-lead + reason in half a sentence. 3-6 items maximum — if
everything is non-negotiable, nothing is.>

- **<Rule>.** <Why, in half a sentence.>

## Procedure — in this order

<Numbered, imperative. Human-approval gates are explicit steps, not
implicit conventions. When order matters, say WHY in one sentence
("X comes LAST because ..."). Reference deep material instead of
inlining it: "-> references/<file>.md".>

0. <Pre-check: does prior state exist? Refine it, don't rewrite.>
1. <Step.>
2. <Step with gate: "-> EXPLICIT user approval before proceeding.">
3. <Computable step: "run scripts/<validator> — don't reason about it.">

## Output contract

<The output SHOWN as a filled example — a real verdict, a real report,
with the real field values. Closed verdict vocabulary + numeric
threshold where applicable ("below 0.7: don't report"). If an
orchestrator parses the result, end with a one-line machine-parsable
report: `RESULT: <value>`. Word budget for subagent briefs: state it.>

```
<filled example output — not a schema, an instance>
```

## [Verbatim blocks — optional]

<Prompts, questions, or report lines that must survive handoffs
unchanged. Mark each: "use this EXACT string — do not paraphrase.">

## [False-positive filtering — optional, review-type skills]

HARD EXCLUSIONS: <numbered list of finding classes auto-rejected>
PRECEDENTS: <case law for the ambiguous calls seen in practice>
<Pipeline: generate -> parallel verify -> numeric threshold cut.>

## [Reference files — optional]

| File | What it answers |
|---|---|
| references/<a>.md | <the question that sends the reader there> |
| scripts/<v>.py | <executable validator — "run it; don't eyeball"> |

## [Anti-patterns — optional]

<"If your output matches an entry, it is wrong — fix before shipping.">

- ❌ <pattern> — <why it misleads> → ✅ <alternative>

## What to leave out

- Anything you didn't run or verify in this repo.
- Generic advice the base model already knows.
- Marketing copy, counts, or history — they change no behavior.
