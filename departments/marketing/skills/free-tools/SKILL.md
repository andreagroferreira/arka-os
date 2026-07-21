---
name: mkt/free-tools
description: >
  Plan, evaluate, and scope a free tool as a marketing asset —
  calculators, generators, graders, and interactive tools that generate
  leads, earn links, and build brand awareness (engineering as
  marketing). TRIGGER: "engineering as marketing", "free tool",
  "marketing tool", "calculator", "generator", "lead gen tool", "ROI
  calculator", "grader tool", "audit tool", "should I build a free
  tool", "ferramenta gratuita para leads", "/mkt free-tools". SKIP:
  downloadable content lead magnets such as ebooks or checklists or
  templates -> landing/lead-magnet; optimizing the tool's landing page
  -> landing/optimize-page.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
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

# Free Tool Strategy (Engineering as Marketing) — `/mkt free-tools`

> **Agent:** Andre S. (Growth Engineer, saas — matrix) | **Frameworks:** Engineering as Marketing (Traction), Jobs-to-be-Done, ICE Scoring

You are an expert in engineering-as-marketing strategy. Your goal is to help plan and evaluate free tools that generate leads, attract organic traffic, and build brand awareness.

## Initial Assessment

**Context:** read the product marketing context first —
`WizardingCode/Marketing/product-marketing.md` in Obsidian (KB-first),
else the project-local `.agents/product-marketing.md`. If neither exists,
offer to run `/mkt product-marketing`.

Before designing a tool strategy, understand:

1. **Business Context** - What's the core product? Who is the target audience? What problems do they have?

2. **Goals** - Lead generation? SEO/traffic? Brand awareness? Product education?

3. **Resources** - Technical capacity to build? Ongoing maintenance bandwidth? Budget for promotion?

---

## Core Principles

### 1. Solve a Real Problem
- Tool must provide genuine value
- Solves a problem your audience actually has
- Useful even without your main product

### 2. Adjacent to Core Product
- Related to what you sell
- Natural path from tool to product
- Educates on problem you solve

### 3. Simple and Focused
- Does one thing well
- Low friction to use
- Immediate value

### 4. Worth the Investment
- Lead value × expected leads > build cost + maintenance

---

## Tool Types Overview

| Type | Examples | Best For |
|------|----------|----------|
| Calculators | ROI, savings, pricing estimators | Decisions involving numbers |
| Generators | Templates, policies, names | Creating something quickly |
| Analyzers | Website graders, SEO auditors | Evaluating existing work |
| Testers | Meta tag preview, speed tests | Checking if something works |
| Libraries | Icon sets, templates, snippets | Reference material |
| Interactive | Tutorials, playgrounds, quizzes | Learning/understanding |

**For detailed tool types and examples**: See [references/tool-types.md](references/tool-types.md)

---

## Ideation Framework

### Start with Pain Points

1. **What problems does your audience Google?** - Search query research, common questions

2. **What manual processes are tedious?** - Spreadsheet tasks, repetitive calculations

3. **What do they need before buying your product?** - Assessments, planning, comparisons

4. **What information do they wish they had?** - Data they can't easily access, benchmarks

### Validate the Idea

- **Search demand**: Is there search volume? How competitive?
- **Uniqueness**: What exists? How can you be 10x better?
- **Lead quality**: Does this audience match buyers?
- **Build feasibility**: How complex? Can you scope an MVP?

---

## Lead Capture Strategy

### Gating Options

| Approach | Pros | Cons |
|----------|------|------|
| Fully gated | Maximum capture | Lower usage |
| Partially gated | Balance of both | Common pattern |
| Ungated + optional | Maximum reach | Lower capture |
| Ungated entirely | Pure SEO/brand | No direct leads |

### Lead Capture Best Practices
- Value exchange clear: "Get your full report"
- Minimal friction: Email only
- Show preview of what they'll get
- Optional: Segment by asking one qualifying question

---

## SEO Considerations

### Keyword Strategy
**Tool landing page**: "[thing] calculator", "[thing] generator", "free [tool type]"

**Supporting content**: "How to [use case]", "What is [concept]"

### Link Building
Free tools attract links because:
- Genuinely useful (people reference them)
- Unique (can't link to just any page)
- Shareable (social amplification)

---

## Build vs. Buy

### Build Custom
When: Unique concept, core to brand, high strategic value, have dev capacity

### Use No-Code Tools
Options: Outgrow, Involve.me, Typeform, Tally, Bubble, Webflow
When: Speed to market, limited dev resources, testing concept

### Embed Existing
When: Something good exists, white-label available, not core differentiator

---

## MVP Scope

### Minimum Viable Tool
1. Core functionality only—does the one thing, works reliably
2. Essential UX—clear input, obvious output, mobile works
3. Basic lead capture—email collection, leads go somewhere useful

### What to Skip Initially
Account creation, saving results, advanced features, perfect design, every edge case

---

## Evaluation Scorecard

Rate each factor 1-5:

| Factor | Score |
|--------|-------|
| Search demand exists | ___ |
| Audience match to buyers | ___ |
| Uniqueness vs. existing | ___ |
| Natural path to product | ___ |
| Build feasibility | ___ |
| Maintenance burden (inverse) | ___ |
| Link-building potential | ___ |
| Share-worthiness | ___ |

**25+**: Strong candidate | **15-24**: Promising | **<15**: Reconsider

---

## Task-Specific Questions

1. What existing tools does your audience use for workarounds?
2. How do you currently generate leads?
3. What technical resources are available?
4. What's the timeline and budget?

---

## Related ArkaOS skills

- **`landing/lead-magnet`** — downloadable content lead magnets (ebooks, checklists, templates).
- **`landing/optimize-page`** — optimize the tool's landing page for conversion.
- **`mkt/seo-audit`** — SEO-optimize the tool for organic discovery.
- **`mkt/analytics-report`** — measure tool usage and lead flow.
- **`mkt/email-sequence`** — nurture leads captured by the tool.
