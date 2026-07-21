---
name: ux-audit
description: >
  UX heuristic audit of a live interface against Nielsen's 10 heuristics and
  Laws of UX — navigates real user flows in the browser, checks accessibility
  and responsive breakpoints, and delivers severity-rated findings with fixes.
  TRIGGER: "ux audit", "audita a usabilidade", "auditoria de UX", "heuristic
  evaluation", "porque é que os users se perdem", "/brand ux-audit <url>".
  SKIP: on-brand visual compliance (palette, typography vs brandbook) ->
  brand/design-review; slow pages or Core Web Vitals -> dev/performance-audit;
  brand strength, not interface -> brand/primal-audit.
metadata:
  origin: community
  source: https://github.com/nutlope/hallmark
  license: MIT
---

# UX Audit

> **Agent:** Sofia D. (UX Designer) | **Framework:** Nielsen 10 Heuristics + Laws of UX
> **Squad reference:** `departments/brand/references/uiux-knowledge-and-tools.md` (§3 tokens, §8 anti-default, §9 marker)

## Load design intelligence (MANDATORY — excellence-mandate)

Do this BEFORE auditing, in this order, and record what actually loaded:

1. **`Skill(ui-ux-pro-max)`** — the 99 UX guidelines are the audit's
   extended checklist beyond Nielsen; cite guideline IDs in findings.
2. **`Skill(frontend-design)`** — calibrates the visual-quality half of
   findings (default-look detection is itself a finding: an interface
   that reads as AI-default gets flagged under aesthetic integrity).
3. **Read the project design system** — findings that violate the
   project's own tokens rank higher than generic advice.
4. **Load the audit references** —
   `../design-review/references/anti-patterns.md` (the named-tell
   dictionary: every AI-slop finding is cited by its named entry and
   Critical/Major/Minor tier) and `../design-review/references/slop-test.md`
   (the 58 mechanical gates; run them on the audited surfaces).

### Graceful degradation (honest, never silent)

If a plugin skill is NOT installed: say so explicitly, fall back to §3 +
§8 of the squad reference, and emit the marker with
`skills=degraded:<missing-name>`. Never claim a load that did not
happen; never proceed as if it had.

## Benchmark first

NAME the reference company this interface should be judged against for
its category (Linear for dashboards, Stripe for checkout/docs, Airbnb
for browse flows…). Every major finding states what the benchmark does
instead.

## Design marker (before any file edit)

```
[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>
```

Emit on its own line BEFORE writing the report. Full contract: §9 of the
squad reference.

## The checklist (applied, not name-dropped)

**Nielsen's 10** — each scored per flow: (1) visibility of system
status; (2) match between system and real world; (3) user control and
freedom (undo/escape); (4) consistency and standards; (5) error
prevention; (6) recognition rather than recall; (7) flexibility and
efficiency (shortcuts, defaults); (8) aesthetic and minimalist design;
(9) help users recognize/recover from errors; (10) help and
documentation.

**Laws of UX (minimum set)** — Fitts (target size/distance), Hick
(choice overload), Jakob (convention violations), Miller (memory load),
Peak-End (how flows end), Aesthetic-Usability (and its trap).

**Severity scale** — 0 not a problem · 1 cosmetic · 2 minor · 3 major
(users fail or abandon) · 4 catastrophic (blocks the core job). Every
finding: heuristic/law violated, severity, evidence (screenshot),
benchmark contrast, concrete fix.

## Workflow

0. **Pre-flight scan (read-only)** — before judging anything, read what
   exists: tokens/theme files, font loads, framework, and the
   `[arka:design-dna]` stamp in produced CSS when present. The audit
   holds the surface to its OWN declared system first, the canonical
   laws second. **The audit never edits** — it documents and ranks;
   fixes belong to the owning build skill.
1. **Scope** — the 2–3 flows that carry the product's core job
   (onboarding, core action, checkout/conversion).
2. **Walk the flows in a real browser** (steps below), capturing
   evidence screenshots per finding.
3. **Score** every screen against the checklist; log findings as you go
   — no memory-based auditing.
4. **Slop pass** — run the 58 gates (`slop-test.md`) and name every hit
   from `anti-patterns.md`; check reflex-reject violations against the
   squad reference §11 and design-law breaches against §12.
5. **Accessibility pass** — keyboard-only run, focus visibility,
   contrast (AA), `prefers-reduced-motion`, semantic landmarks.
6. **Responsive pass** — 390 / 768 / 1440; layout integrity, target
   sizes, content parity.
7. **Report** — findings ranked by severity, quick-wins vs structural,
   each with its fix and benchmark contrast. Header line:
   `Summary — N critical · M major · K minor`; close with the verdict
   line `Verdict — [ships as slop | reads as AI-generated | close, fix
   the minors | clean]`.

## Browser Steps

Follow the Browser Integration Pattern for availability checking.

- [BROWSER] Navigate the site following primary user flows (onboarding, core action, checkout)
- [BROWSER] Test accessibility: tab navigation, focus indicators, color contrast
- [BROWSER] Capture screenshots of key screens for the UX audit report
- [BROWSER] Check responsive design at mobile, tablet, and desktop breakpoints
- [BROWSER] Verify loading states, error states, and empty states render correctly

## Computer Use Steps

Follow the Computer Use Availability Check for availability checking.

- [COMPUTER] Launch the native app, test user flows, screenshot each screen for the audit report

## Output

Heuristic audit report: severity-ranked findings (heuristic/law +
evidence screenshot + benchmark contrast + fix), accessibility and
responsive annexes, quick-win list. Saved to Obsidian under the
project's UX path.

## Scheduling ⏰

```
/schedule weekly — run Lighthouse audit on main pages, flag performance regressions
/schedule monthly — full UX heuristic review of core user flows
```
