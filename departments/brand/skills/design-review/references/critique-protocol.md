# Critique Protocol — Isolated Dual-Review Design Critique

> Derived from [impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0 — see `impeccable.LICENSE` and `impeccable.NOTICE` in this directory). Distilled and adapted for ArkaOS; changes from upstream are substantial (orchestration kept, CLI plumbing removed).

## Purpose

Resolve one stable target (a source file path over a dev-server URL — ports drift, paths do not), run two independent assessments, and synthesize a design critique the way a design director would deliver it. The chat report is the deliverable.

## Hard Invariants

- Assessment A (LLM design review) and Assessment B (deterministic detector + browser evidence) are BOTH required.
- A and B MUST run as two isolated subagents whenever dispatch is available. Running them inline is "possible" but NOT permitted — it is a degraded run. Inline is allowed only when no subagent dispatch exists.
- If you degrade for any reason, the report's FIRST line must be the banner: `⚠️ DEGRADED: single-context (<reason>)`. A silent degraded critique is a failed critique.
- Assessment A must finish before detector findings enter the synthesis context. Detector output is deterministic, but it still anchors judgment.
- A skipped detector is a failed critique run unless the detector is genuinely missing or crashes after a real attempt.
- Viewable targets require browser inspection when browser automation is available.
- Never claim a user-visible overlay or visual evidence exists unless the browser step actually produced it.

## Orchestration — Two Isolated Subagents

Dispatch two isolated review subagents (quality dispatches are exempt from subagent-discipline caps — independent review context is a correctness requirement). They MUST NOT see each other's output; do not show findings to the user until synthesis.

- **Sub-agent A — Design review.** Reads relevant source files and visually inspects the live page when browser automation is available. Blind to detector output.
- **Sub-agent B — Deterministic evidence.** Runs the deterministic design-slop detector (QG check `design-slop`, Wave 3) plus browser evidence. Blind to A's judgment.

Rules of engagement:

- Spawn A and B in parallel whenever dispatch is available. "Unavailable" means exactly one thing: no subagent dispatch is exposed in this session. It does not mean inconvenient, and never "faster inline".
- If and only if dispatch is unavailable, fall back sequentially: finish and record Assessment A, then run Assessment B, then synthesize — and emit the degraded banner.
- Whichever path was taken, declare it in the report header (see provenance below). Skipping isolation without the banner is the most common failure of this protocol.
- If browser automation is available, each assessment opens its own fresh tab. Never reuse an existing tab, even if it is already at the right URL.

## Assessment A: Design Review

Think like a design director. Evaluate:

- **AI slop** — would someone believe "AI made this" immediately? Apply the anti-slop doctrine and the register-specific slop tests (see `design-registers.md`).
- **Holistic design** — hierarchy, IA, emotional fit, discoverability, composition, typography, color, accessibility, states, copy, edge cases.
- **Cognitive load** — apply the working-memory rule and the 8-item checklist below; report checklist failures and any decision point with >4 visible options.
- **Emotional journey** — peak-end rule, emotional valleys, reassurance at high-stakes moments.
- **Nielsen heuristics** — score all 10 heuristics 0–4. Score against Nielsen's 10 heuristics — the squad's canonical source is [[Area 02 - Design]] and the ui-ux-pro-max plugin.

Return contract: AI slop verdict, heuristic scores, cognitive load result, emotional journey notes, 2–3 strengths, 3–5 priority issues, persona red flags, minor observations, provocative questions.

## Assessment B: Detector + Browser Evidence

Run the deterministic design-slop detector (QG check `design-slop`, Wave 3) against the target markup, and gather browser evidence when the target is viewable and automation is available (fresh tab, screenshot, console/state observations on 3–5 representative pages for multi-view targets).

Return contract: detector findings with counts, rule names, and file locations; browser observations if applicable; suspected false positives; skipped or failed steps with concrete reasons. Reuse B's detector findings in synthesis — do not rerun the detector in the parent unless B failed, was truncated, or omitted counts, rule names, or locations.

## Synthesis — Combined Critique Report

Synthesize both assessments into a single report. Do NOT concatenate. Weave the findings: note where the LLM review and the detector agree, where the detector caught issues the LLM missed, and where detector findings are false positives. Present the full structured critique in chat — never a summary plus a link.

### Report header provenance

The report's first line MUST declare how the assessments ran, so a degraded run is never silent:

- Dual-agent: `Method: dual-agent (A: <agent-id> · B: <agent-id>)`
- Degraded: `⚠️ DEGRADED: single-context (<reason, e.g. no subagent dispatch exposed>)`

### Design Health Score

Present the Nielsen scores as a table (canonical heuristics source: [[Area 02 - Design]] + ui-ux-pro-max):

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | ? | [specific finding or "n/a" if solid] |
| 2 | Match System / Real World | ? | |
| 3 | User Control and Freedom | ? | |
| 4 | Consistency and Standards | ? | |
| 5 | Error Prevention | ? | |
| 6 | Recognition Rather Than Recall | ? | |
| 7 | Flexibility and Efficiency | ? | |
| 8 | Aesthetic and Minimalist Design | ? | |
| 9 | Error Recovery | ? | |
| 10 | Help and Documentation | ? | |
| **Total** | | **??/40** | **[Rating band]** |

### Report sections, in order

1. **Anti-Patterns Verdict** — start here. Does this look AI-generated? Give the LLM assessment (aesthetic feel, layout sameness, generic composition, missed personality) AND the deterministic scan summary (counts, locations, false positives flagged).
2. **Overall Impression** — gut reaction: what works, what doesn't, the single biggest opportunity.
3. **What's Working** — 2–3 things done well, specific about why.
4. **Priority Issues** — the 3–5 most impactful problems, ordered. Each tagged `[P0–P3]` with: **What** (name it), **Why it matters** (user/goal impact), **Fix** (concrete).
5. **Persona Red Flags** — 2–3 personas from the selection table below; name the exact elements and interactions that fail each persona, never generic descriptions.
6. **Minor Observations** — quick notes on smaller issues.
7. **Questions to Consider** — provocative unlocks: "What if the primary action were more prominent?" "Does this need to feel this complex?" "What would a confident version of this look like?"

## Scoring Mechanics (0–4)

Each heuristic scores 0–4: **0** = broken/absent, **1** = rare/mostly failing, **2** = partial with major gaps, **3** = good with minor gaps, **4** = genuinely excellent. Total out of 40:

| Score Range | Rating | What It Means |
|-------------|--------|---------------|
| 36–40 | Excellent | Minor polish only; ship it |
| 28–35 | Good | Address weak areas, solid foundation |
| 20–27 | Acceptable | Significant improvements needed before users are happy |
| 12–19 | Poor | Major UX overhaul required; core experience broken |
| 0–11 | Critical | Redesign needed; unusable in current state |

## Honesty Rubric

- Be honest with scores. A 4 means genuinely excellent, not "good enough". Most real interfaces score 20–32.
- Be direct. Vague feedback wastes everyone's time.
- Be specific. "The submit button," not "some elements."
- Say what's wrong AND why it matters to users.
- Give concrete suggestions. Cut "consider exploring..." entirely.
- Prioritize ruthlessly. If everything is important, nothing is.
- Don't soften criticism. Builders need honest feedback to ship great design.

## Issue Severity (P0–P3)

| Priority | Name | Description | Action |
|----------|------|-------------|--------|
| **P0** | Blocking | Prevents task completion entirely | Fix immediately; showstopper |
| **P1** | Major | Causes significant difficulty or confusion | Fix before release |
| **P2** | Minor | Annoyance, but workaround exists | Fix in next pass |
| **P3** | Polish | Nice-to-fix, no real user impact | Fix if time permits |

Tie-breaker: "Would a user contact support about this?" If yes, it's at least P1.

## Cognitive Load — Working Memory Rule + Checklist

**Humans hold ≤4 items in working memory at once** (Miller's Law, revised by Cowan 2001). At any decision point, count distinct options/actions/facts the user must hold simultaneously: ≤4 manageable · 5–7 pushing the boundary (group or disclose progressively) · 8+ overloaded (users skip, misclick, abandon). Practical caps: ≤5 top-level nav items, ≤4 form fields per visual group, 1 primary + 1–2 secondary actions, ≤4 dashboard metrics without scrolling, ≤3 pricing tiers.

Checklist — evaluate all 8:

- [ ] **Single focus**: can the user complete the primary task without competing elements?
- [ ] **Chunking**: information in digestible groups (≤4 items per group)?
- [ ] **Grouping**: related items visually grouped (proximity, borders, shared background)?
- [ ] **Visual hierarchy**: immediately clear what's most important?
- [ ] **One thing at a time**: single decision at a time before moving on?
- [ ] **Minimal choices**: ≤4 visible options at any decision point?
- [ ] **Working memory**: no remembering info from a previous screen to act on this one?
- [ ] **Progressive disclosure**: complexity revealed only when needed?

Scoring: count failures. 0–1 = low load (good) · 2–3 = moderate (address soon) · 4+ = high (critical fix).

## Persona-Based Design Testing

Test through 2–3 archetypes; each exposes failure modes a single design-director lens misses. Walk the primary user action as each persona and report specific red flags — exact elements, not generic concerns.

**1. Alex — Impatient Power User.** Expert with similar products; skips onboarding, hunts keyboard shortcuts, tries bulk/batch actions, abandons anything slow or patronizing. Red flags: forced tutorials or unskippable onboarding · no keyboard navigation for primary actions · slow unskippable animations · one-item-at-a-time workflows where batch would be natural · redundant confirmations for low-risk actions.

**2. Jordan — Confused First-Timer.** Never used this product type; reads everything, hesitates before unfamiliar clicks, takes labels literally, abandons rather than figures it out. Red flags: icon-only navigation with no labels · technical jargon without explanation · no visible help or guidance · ambiguous next steps after an action · no confirmation that an action succeeded.

**3. Sam — Accessibility-Dependent User.** Screen reader (VoiceOver/NVDA), keyboard-only, may use 200% zoom; needs 4.5:1 contrast, ARIA labels, heading structure, announced state changes. Red flags: click-only interactions with no keyboard alternative · missing or invisible focus indicators · meaning conveyed by color alone · unlabeled form fields or buttons · time-limited actions without extension · custom components that break screen-reader flow.

**4. Riley — Deliberate Stress Tester.** Pushes past the happy path: empty states, long strings, emoji/RTL input, refresh mid-flow, multiple tabs; documents gaps between what the UI promises and what happens. Red flags: features that appear to work but silently fail · error handling that exposes technical detail or bricks the UI · empty states with no guidance · workflows that lose data on refresh or navigation · inconsistent behavior between similar interactions.

**5. Casey — Distracted Mobile User.** One thumb, on the go, interrupted mid-flow, possibly on 3G; taps over typing, expects state preserved on return. Red flags: primary actions at the top of the screen (out of thumb zone) · no state persistence across interruptions · large text inputs where selection would work · heavy assets with no lazy loading · tiny or crowded tap targets (<44×44pt).

### Persona selection table

| Interface Type | Primary Personas | Why |
|---------------|-----------------|-----|
| Landing page / marketing | Jordan, Riley, Casey | First impressions, trust, mobile |
| Dashboard / admin | Alex, Sam | Power users, accessibility |
| E-commerce / checkout | Casey, Riley, Jordan | Mobile, edge cases, clarity |
| Onboarding flow | Jordan, Casey | Confusion, interruption |
| Data-heavy / analytics | Alex, Sam | Efficiency, keyboard nav |
| Form-heavy / wizard | Jordan, Sam, Casey | Clarity, accessibility, mobile |

When the project carries real audience/brand context (project design system, brand descriptor), derive 1–2 project-specific personas from it — profile, behaviors, red flags. Never invent audience details; without real context, use only the 5 predefined personas.

## After the Report

Ask 2–4 targeted questions grounded in actual findings (priority direction among the found issue categories, design intent on tonal mismatches, scope: top-3 vs all, off-limits areas). Never ask generic "who is your audience?" questions; offer concrete options. If findings are trivial (1–2 clear issues), skip questions and go straight to a prioritized action list mapped to the issues, ordered by the user's stated priorities, then impact.
