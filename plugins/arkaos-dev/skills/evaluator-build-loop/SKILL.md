---
name: evaluator-build-loop
description: >
  Adversarial build loop for UI work: a generator implements against a
  weighted rubric while an independent, ruthless evaluator tests the LIVE
  app in a real browser — not the code, not screenshots — and the loop
  repeats until the score clears the threshold. TRIGGER: "/dev
  evaluator-build-loop", "build until it passes", "itera até passar",
  "loop de UI", "evaluator loop", "faz e avalia até estar excelente"; any
  UI build where the excellence-mandate visual benchmark applies and the
  operator wants convergence without babysitting. SKIP: one-shot review
  of an existing diff -> dev/code-review wins; UX audit of a shipped page
  without a build loop -> dev/click-path-audit wins; writing E2E suites
  -> dev/app-test wins.
metadata:
  origin: arkaos
---

# Evaluator Build Loop

> **Agents:** Diana (Frontend, generator) + Rita (QA, evaluator) | **Framework:** Generator–evaluator separation, rubric-driven iteration

The dev server is up, the screenshot looks fine, and the agent that built
the page declares it done. Then someone clicks the second tab, resizes to
390px, or submits the form empty — and the illusion collapses. Builders
grade their own work with the same eyes that produced it, which is why
this loop never lets them. One role writes; a different role, in a fresh
context, tries to make the page fail.

## Roles — never merged, never shared

| Role | Agent | Contract |
|---|---|---|
| **Generator** | Diana | Reads the spec + the latest `feedback-NNN.md`; fixes EVERY open finding in order — functionality → craft → design → originality; keeps the dev server alive; commits once per iteration. |
| **Evaluator** | Rita | Fresh subagent per iteration, launched with ONLY the spec, the rubric, and the app URL — never the generator's reasoning. Drives the live app via the Playwright MCP. Scores against the rubric; writes the next `feedback-NNN.md`. |

The evaluator's launch context is the mechanism, not a detail: any shared
reasoning re-imports the generator's blind spots.

## The rubric

Written BEFORE iteration 1, with explicit weights, from the spec plus the
project design system and a named visual benchmark (excellence-mandate:
UI work loads frontend-design, ui-ux-pro-max, and the project design
system at maximum effort). Typical weighting: functionality 40 · craft
(states, a11y, responsiveness) 30 · design fidelity 20 · originality 10.
A dimension the spec does not care about gets weight 0 — do not invent
criteria mid-loop.

The craft dimension is not vibes: the evaluator cites the 58 slop gates
(`departments/brand/skills/design-review/references/slop-test.md`) and
the design laws (doctrine hub §12) by number when scoring — a gate hit
caps the craft score for that iteration.

## Evaluator discipline

- Test the **live app** in the browser: click paths, keyboard, empty and
  error states, viewport extremes. Not the code. Not screenshots.
- Be ruthless by instruction: hunt the edge case, penalize
  default-looking output, refuse partial credit for "almost works".
- **Default-refuted:** when unsure whether a criterion passes, it fails.
  Optimism is the generator's disease; the evaluator is the cure.
- Every finding names the concrete reproduction — URL, action, expected
  vs. observed — so the generator fixes instead of guessing.

## Loop mechanics

1. Generator builds iteration N; commits on the working branch; emits the
   `[arka:design]` evidence marker (frontend gate).
2. Evaluator (fresh context) scores the live app → `feedback-NNN.md` with
   the score per dimension and ranked findings.
3. Score ≥ threshold (default 90/100) → exit to Quality Gate. Otherwise
   loop.
4. **Circuit breaker:** 5 iterations without clearing the threshold, or
   two consecutive iterations with no score improvement → stop and
   escalate to the operator with the score history. Never grind silently.

All handoff is by file — spec, rubric, feedback — so the loop survives a
`/clear` and either role can be resumed cold.

## Output

```markdown
## Evaluator Build Loop Report

**Spec:** {path} | **Rubric threshold:** {n}
**Iterations:** {k} | **Final score:** {score}/100

| Iter | Functionality | Craft | Design | Originality | Total |
|---|---|---|---|---|---|

**Open findings:** {none, or the escalation list with reproductions}
**Evidence:** commits {range}, feedback files, `[arka:design]` markers
```

The loop feeds the Quality Gate; it does not replace it. Marta still has
the veto.
