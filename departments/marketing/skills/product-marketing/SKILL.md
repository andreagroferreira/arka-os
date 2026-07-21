---
name: mkt/product-marketing
description: >
  Create and maintain the product marketing context document — the
  shared positioning, ICP, and messaging file that every other marketing
  skill reads first. TRIGGER: "product context", "marketing context",
  "positioning", "quem é o meu público-alvo", "ICP", "ideal customer
  profile", "define o produto", "set up context", "/mkt product-marketing".
  Run this at the start of any new marketing engagement before the other
  skills. SKIP: buyer/user persona depth as a research artifact ->
  kb/persona-build (this captures positioning context, that builds a
  persona); competitor teardown -> mkt/competitor-analysis; brand voice
  system as a standalone deliverable -> brand/voice-guide.
allowed-tools: [Read, Write, Edit, Grep, Glob, Agent]
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Product Marketing Context — `/mkt product-marketing`

> **Agent:** Lourenço (Product Marketing Manager) | **Frameworks:** Obviously Awesome (Dunford), JTBD Four Forces, Schwartz 5 Levels

You create and maintain the **product marketing context document** — the
foundational positioning and messaging file that every other marketing
skill reads before it acts, so the user never repeats product, audience,
or positioning basics across tasks.

## Where the context lives (the ArkaOS contract)

This is the standard **Context block** every marketing skill in ArkaOS
opens with. Resolution order:

1. **Canonical (KB-first):** the Obsidian note
   `WizardingCode/Marketing/product-marketing.md`. Read it via
   `mcp__obsidian__read_note` / `mcp__obsidian__search_notes`.
2. **Project-local fallback:** `.agents/product-marketing.md` in the
   working repo (and the legacy `.claude/product-marketing.md` /
   `product-marketing-context.md` names — offer to migrate to the
   canonical Obsidian note if found).
3. **Missing:** offer to build it now with this skill.

When you save, write BOTH: the Obsidian note is the source of truth; a
project-local `.agents/product-marketing.md` copy stays in the repo the
work targets so tool-only sessions without vault access still resolve it.

## Workflow

### Step 1 — Check for existing context

Check the Obsidian note first, then the project-local fallbacks. **If it
exists:** read it, summarize what is captured, note the current
**Document version** and the last few **Changelog** entries, ask which
sections to update, and only gather for those. On any substantive save,
bump the version and prepend a changelog entry (Step 4).

**If it does not exist, offer two paths:**

1. **Auto-draft from the codebase / vault** (recommended): study the
   repo (README, landing pages, marketing copy, `package.json`) and any
   existing Obsidian notes on the product, draft a V1, then ask "What
   needs correcting? What's missing?"
2. **From scratch:** walk each section conversationally, one at a time.

### Step 2 — Gather information

Push for **verbatim customer language** — exact phrases beat polished
descriptions because copy resonates when it mirrors how customers
actually speak. Draft or ask one section at a time; confirm before
moving on.

## Sections to capture

1. **Product Overview** — one-liner, what it does, product category (the
   "shelf" customers search on), product type, business model & pricing.
2. **Target Audience** — company type, decision-makers, primary use case,
   jobs-to-be-done, specific scenarios.
3. **Personas (B2B)** — for each stakeholder (User, Champion, Decision
   Maker, Financial Buyer, Technical Influencer): what they care about,
   their challenge, the value promised.
4. **Problems & Pain Points** — core challenge before finding you, why
   current solutions fall short, what it costs (time/money/opportunity),
   emotional tension.
5. **Competitive Landscape** — direct (same solution/problem), secondary
   (different solution/same problem), indirect (conflicting approach);
   how each falls short.
6. **Differentiation** — capabilities alternatives lack, how you solve it
   differently, why that is better, why customers choose you.
7. **Objections & Anti-Personas** — top 3 sales objections + responses;
   who is NOT a fit.
8. **Switching Dynamics (JTBD Four Forces)** — Push, Pull, Habit, Anxiety.
9. **Customer Language** — verbatim problem/solution phrasing, words to
   use, words to avoid, glossary.
10. **Brand Voice** — tone, communication style, 3–5 personality
    adjectives (align with `brand/voice-guide` if one exists).
11. **Proof Points** — metrics/results, notable customers, testimonial
    snippets, value themes + evidence.
12. **Goals** — primary business goal, key conversion action, current
    metrics.

### Step 3 — Create the document

Write the note with versioned frontmatter and the 12 sections above,
ending with a **Changelog** (newest first, one line per revision). Use
the section templates (tables for Personas / Objections / Glossary /
Proof themes) so downstream skills can parse it.

### Step 4 — Confirm, version, save

- Show the completed document; ask what to adjust.
- **New document:** `Document version: v1` + one changelog entry
  `- v1 (YYYY-MM-DD) — Initial context.`
- **Update:** increment the version, set `Last updated` to today,
  **prepend** a changelog entry naming the sections touched and the
  reason (never rewrite past entries). Typo-only fixes do not bump.
- Save to the Obsidian canonical note AND the project-local
  `.agents/product-marketing.md`.
- Tell the user: "Every other `/mkt`, `/landing`, `/saas`, and `/sales`
  marketing skill now reads this context automatically. Run
  `/mkt product-marketing` anytime to update it."

## Output → Obsidian

`WizardingCode/Marketing/product-marketing.md` (canonical) + project-local
`.agents/product-marketing.md` mirror.

## Related ArkaOS skills

- **mkt/marketing-plan** — turns this context into a 12-month AARRR plan.
- **mkt/competitor-analysis** — deepens section 5.
- **landing/copy-framework**, **landing/optimize-page** —
  all read this context before generating copy.
- **kb/persona-build** — builds a full research persona from the ICP here.
