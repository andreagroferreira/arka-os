---
name: kb/research-plan
description: >
  Plans and executes structured research: defines the question, gathers
  academic/industry/expert sources, evaluates them with the CRAAP test,
  synthesizes findings, and documents everything in Obsidian. TRIGGER: "faz
  research sobre X", "investiga este tema a fundo", "research plan for X",
  "plan a literature review", "/kb research <topic>". SKIP: AI-tool-driven
  source gathering (Perplexity, Elicit) -> kb/ai-research (the AI-tooling arm
  of this process); rating a single source -> kb/source-evaluate (one CRAAP
  score, not a full study); competitor dossiers -> kb/competitive-intel
  (battlecards, not open research).
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Research Plan — `/kb research <topic>`

> **Agent:** Francisco (Research Analyst) | **Framework:** Research Methodology + CRAAP Test

## 5-Step Research Process

### 1. Define the Question
- What specifically do we need to know?
- Why? What decision depends on this?
- What's the scope (broad survey vs deep dive)?

### 2. Gather Sources
- Academic: Google Scholar, research papers
- Industry: Reports, surveys, benchmarks
- Expert: Books, talks, interviews
- AI-assisted: Perplexity, Elicit, Claude
- Primary: Customer interviews, surveys

### 3. Evaluate Sources (CRAAP Test)

| Criterion | Question | Score 1-5 |
|-----------|----------|-----------|
| **C**urrency | How recent? Still relevant? | |
| **R**elevance | Does it address our specific question? | |
| **A**uthority | Who wrote it? Credible? Expert? | |
| **A**ccuracy | Evidence-based? Peer-reviewed? Verifiable? | |
| **P**urpose | Objective or biased? Selling something? | |

**Score 20-25:** Highly reliable. **15-19:** Usable with caveats. **Below 15:** Discard.

### 4. Synthesize
- Extract key findings across sources
- Identify agreements and contradictions
- Formulate conclusions with confidence levels
- Note gaps (what we still don't know)

### 5. Document
- Research report saved to Obsidian
- All sources linked with CRAAP ratings
- Cross-reference with existing KB notes
- Update relevant MOCs

## Output → Obsidian: `🧠 Knowledge Base/Research/RESEARCH-<topic>-<date>.md`
