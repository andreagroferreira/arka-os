---
name: primal-audit
description: >
  Audits an existing brand against Patrick Hanlon's 7 Primal Code elements
  using a 21-point evidence-cited rubric, a competitor benchmark, and a ranked
  remediation plan. TRIGGER: "audita a marca", "brand audit", "primal audit",
  "quão forte é a nossa marca", "how strong is our brand", "/brand audit".
  SKIP: auditing the interface, not the brand -> brand/ux-audit (Nielsen
  heuristics on usability); no brand exists yet to audit ->
  brand/identity-system (creation, not audit).
---

# Primal Brand Audit

> **Agent:** Mateus (Brand Strategist) | **Framework:** Primal Branding (Patrick Hanlon)

## The 7 Primal Code Elements

| # | Element | Question | Status |
|---|---------|----------|--------|
| 1 | **Creation Story** | How was the brand born? Is it told consistently? | |
| 2 | **Creed** | What does the brand believe? Core principles? | |
| 3 | **Icons** | What visual symbols are instantly associated? | |
| 4 | **Rituals** | What repeated interactions define the experience? | |
| 5 | **Non-Adherents** | Who is the opposition? What are we NOT? | |
| 6 | **Sacred Lexicon** | What special language do believers use? | |
| 7 | **Leader** | Who embodies the brand values? Visible face? | |

## Audit Process

1. **Gather** — Collect all brand assets: website, social, packaging, internal docs
2. **Map** — Fill each of the 7 elements with what currently exists
3. **Score** — Apply the per-element rubric below (3 points each across 7 elements = 21 total)
4. **Gaps** — Identify weak elements and the specific sub-criterion that failed
5. **Recommend** — Specific remediation per gap, ranked by leverage
6. **Benchmark** — Compare against 3-5 competitors' Primal Codes

## Per-Element Scoring Rubric (3 sub-criteria each)

Each element is scored 0-3. Mark each sub-criterion present (1) or absent (0); sum to the element score.

### 1. Creation Story (max 3)
- [ ] **Origin moment is named** — a specific event, year, person, or pain point that triggered the brand
- [ ] **Consistency across surfaces** — the same story appears on About page, founder bio, key talks
- [ ] **Emotional anchor present** — a stakes-laden tension the founder needed to resolve

### 2. Creed (max 3)
- [ ] **Belief is stated, not implied** — explicit "we believe…" or "we exist because…" sentence
- [ ] **Belief has a counter-position** — the creed names what it rejects, not just what it affirms
- [ ] **Belief shapes product decisions** — at least one shipped feature can be traced to the creed

### 3. Icons (max 3)
- [ ] **Symbol is consistent** — same logo / mark across all primary surfaces
- [ ] **Symbol carries meaning** — the mark is decoded by users (Apple = bite, Nike = motion)
- [ ] **Sub-icons reinforce** — secondary visual language (palette, type, photography style) supports the primary symbol

### 4. Rituals (max 3)
- [ ] **Repeated user action defines the brand** — unboxing, onboarding, daily check-in, signature gesture
- [ ] **The ritual is named or recognizable** — users can describe the ritual back without prompting
- [ ] **The ritual is protected** — the brand resists altering it; the ritual has loadbearing weight

### 5. Non-Adherents (max 3)
- [ ] **Opposition is named** — competitors, mindsets, or status-quo positions explicitly called out
- [ ] **Identity is sharpened by contrast** — what the brand REFUSES is as clear as what it offers
- [ ] **Tribal lines are visible to outsiders** — adopting the brand signals belonging in a recognizable in-group

### 6. Sacred Lexicon (max 3)
- [ ] **3+ proprietary terms in active use** — words coined or claimed by the brand that customers repeat
- [ ] **Vocabulary is taught** — onboarding, docs, or messaging explicitly introduce the lexicon
- [ ] **Outsiders cannot fake fluency** — using the lexicon correctly signals real adherence

### 7. Leader (max 3)
- [ ] **A named human embodies the brand** — founder, CEO, public face with personal voice
- [ ] **Leader carries the creed** — public statements consistently align with the brand's belief
- [ ] **Leader is accessible** — direct contact channel exists (writing, podcast, social presence, AMAs)

## 21-Point Index

| Score | Rating | Meaning |
|-------|--------|---------|
| 18-21 | Iconic | Brand has cult-like following potential |
| 14-17 | Strong | Well-defined, minor gaps to fill |
| 10-13 | Developing | Foundation exists, significant gaps |
| 0-9 | Underdeveloped | Major brand building needed |

## Evidence Citation Contract

Every per-criterion score MUST cite specific asset evidence. Format:

```
Creation Story (2/3)
  ✓ Origin moment named — "Founded 2018 in a coffee shop after the third
    failed deploy" (About page, 2nd paragraph)
  ✓ Consistency across surfaces — same story on About + founder LinkedIn
    + S2 podcast appearance
  ✗ Emotional anchor present — origin reads as biography, no stakes-laden
    tension. Suggested remediation: rewrite to surface the cost of the
    problem (what was at risk if this didn't exist).
```

A score without evidence is a score without weight. Self-critique phase rejects any unjustified marks.

## Competitor Benchmark Template

For each of 3-5 competitors, complete the same 21-point rubric and compute relative position:

```
| Brand | Creation | Creed | Icons | Rituals | Non-Adherents | Lexicon | Leader | Total |
|-------|----------|-------|-------|---------|---------------|---------|--------|-------|
| Ours  |   2      |   3   |   2   |   1     |   0           |   2     |   3    | 13/21 |
| CompA |   3      |   3   |   3   |   3     |   2           |   3     |   2    | 19/21 |
| CompB |   1      |   2   |   2   |   1     |   1           |   1     |   1    |  9/21 |
| CompC |   2      |   2   |   3   |   2     |   2           |   2     |   1    | 14/21 |
```

Output **strategic gaps** (where we trail the leader) vs **deliberate non-positions** (where we choose not to compete). Mark each gap with leverage rating: high / medium / low — to be ranked into the remediation plan.

## Output → Obsidian: `WizardingCode/Brand/Audits/PRIMAL-AUDIT-<brand>-<date>.md`

Includes: per-element scoring with citations, 21-point index, competitor benchmark, ranked remediation plan with leverage ratings, and concrete next-7-days actions for the top 3 gaps.
