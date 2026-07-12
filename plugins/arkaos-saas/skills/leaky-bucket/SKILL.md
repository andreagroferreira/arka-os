---
name: leaky-bucket
description: >
  Leaky-Bucket gate — pass/fail audit of churn, NRR, and activation BEFORE
  approving acquisition spend, with LTV compounding math; every 1% of churn
  compounds against LTV forever. Owned by the RevOps squad. TRIGGER:
  "leaky bucket", "podemos aumentar o investimento em aquisição?", "should
  we scale acquisition", "gate de retenção antes do CAC", "check NRR before
  spending", "/saas leaky-bucket". SKIP: gate failed and you need root
  causes -> saas/churn-analysis (cohort diagnosis, not verdict); fixing the
  activation drop-off itself -> saas/onboarding-optimize.
---

# Leaky-Bucket Gate

> **Agent:** Vicente (RevOps Lead) + Patricia (Head of CS) · **Framework:** Leaky Bucket / Retention-first
> KB: [[Leaky-Bucket Diagnostic]] · [[Retention Flywheel]] · [[Atendimento Como Gerador de Receita]]

A **gate** to run before any acquisition campaign or CAC increase. If the bucket leaks, more traffic just leaks faster.

## The gate (pass/fail before acquisition)
1. **Measure current churn** (logo + revenue) vs benchmark: B2C 5-7%/mo, B2B 1-2%/mo, Enterprise <1%/mo.
2. **NRR check:** is Net Revenue Retention > 100%? If < 100%, expansion is not covering churn → **gate fails**.
3. **Activation check:** time-to-first-value and activation rate healthy? Most churn happens between onboarding and the first quick win (48-72h).
4. **Compounding math:** show LTV at current churn vs LTV at target churn. A 1-point churn improvement usually beats a 1-point CAC improvement.

## Verdict
- **PASS** → acquisition is approved; the new revenue will stick.
- **FAIL** → freeze/limit acquisition; route to the Retain & Recover missions to fix onboarding, NRR and win-back first, then re-run the gate.

## Output
A short gate report (churn, NRR, activation, LTV-at-current-vs-target) + verdict, in Obsidian. Wire into the Acquire mission as a pre-condition.
