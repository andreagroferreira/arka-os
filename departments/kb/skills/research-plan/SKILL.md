---
name: kb/research-plan
description: >
  Plan and execute research with source evaluation (CRAAP test),
  synthesis, and Obsidian documentation.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
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
