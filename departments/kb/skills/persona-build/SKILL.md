---
name: kb/persona-build
description: >
  Builds or refines a callable persona from KB content: source inventory, cited
  belief inventory, voice signature, expertise map, decision patterns, and
  4-framework behavioral DNA (DISC + Enneagram + Big Five + MBTI), shipped as
  a callable advisor YAML. TRIGGER: "cria uma persona do X", "constrói o
  advisor", "build a persona from these sources", "extract his voice and
  beliefs", "/kb persona <name>". SKIP: writing content in an existing
  persona's voice -> kb/write-as-persona (uses a persona, does not build one);
  ingesting new source material first -> kb/learn-content (ingestion precedes
  persona extraction).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Persona Build — `/kb persona <name>`

> **Lead:** Clara (Knowledge Director) | **Cross-dept:** Pedro (Research Analyst) + Eduardo (Copy Director) | **Frameworks:** Persona DNA (DISC + Enneagram + Big Five + MBTI) + Voice Pattern Extraction + Source-Cited Belief Inventory

## What ships

A production callable persona in 7 deliverables:

1. **Source inventory** — every input file/URL tagged by type + date
2. **Belief inventory** — core beliefs with source citations per belief
3. **Voice pattern** — N-gram signature + recurring phrases + structural rhythm + no-go words
4. **Expertise map** — deep / surface / no-go domain classification
5. **Decision pattern catalogue** — characteristic evaluation patterns with cited examples
6. **4-framework Behavioral DNA** — DISC + Enneagram + Big Five + MBTI scored from evidence
7. **Callable advisor YAML** — ready to invoke from any /arka command

## Source Inventory Format

Every persona source is tagged:

```yaml
sources:
  - id: source-001
    url: <url or local path>
    type: talk | interview | written | social | podcast | book
    date: YYYY-MM-DD
    weight: high | medium | low   # based on persona's intent + content depth
    summary: <one-line description>
```

Minimum source diversity for a credible persona: 5 sources across at least 3 types, spanning at least 6 months of date range.

## Belief Inventory (cited extraction)

A belief is a claim the persona has made consistently across multiple sources. Format:

```yaml
beliefs:
  - statement: "<the belief in plain language>"
    strength: load-bearing | supporting | aspirational
    citations:
      - source: source-003
        quote: "<verbatim>"
      - source: source-007
        quote: "<verbatim>"
    counter-position: <what this belief rejects, if explicit>
```

Beliefs without 2+ citations are dropped — single-mention statements are not strong enough to be a persona trait. Load-bearing beliefs (the ones the persona cannot abandon without becoming someone else) require 4+ citations.

## Voice Pattern Extraction

The voice signature has 4 layers:

### 1. Lexical signature (vocabulary)
- **Proprietary terms** — words the persona uses unusually often or coined
- **Forbidden words** — words the persona never uses (often due to belief)
- **N-gram patterns** — 2-3 word phrases that recur in characteristic positions

### 2. Syntactic signature (sentence structure)
- Average sentence length
- Clause complexity (simple / compound / complex preferred)
- Sentence-opening patterns (3-5 typical openers)
- Sentence-closing patterns (3-5 typical closes)

### 3. Rhetorical signature (argumentation pattern)
- Preferred argument structure (claim-evidence-warrant vs Socratic vs analogy-driven vs storytelling)
- Use of qualifiers (hedged vs declarative)
- Use of self-disclosure (front-loaded / withheld / never)

### 4. Tonal signature (emotional register)
- Default warmth (cold / neutral / warm)
- Default certainty (hedged / measured / declarative)
- Humor pattern (none / wry / direct / self-deprecating)
- Confrontation pattern (avoided / oblique / direct)

Each layer must be derivable from at least 3 source examples.

## Expertise Map

Three concentric domains:

```yaml
expertise:
  deep:
    - domain: <area>
      evidence: <which sources prove deep expertise>
      sub-domains: [<list>]
  surface:
    - domain: <area>
      evidence: <touched briefly in sources>
  no-go:
    - domain: <area>
      reason: <why this persona refuses to opine here>
      citation: <source where they explicitly declined>
```

A persona that opines on everything has no persona — the no-go list is as important as the deep list.

## Decision Patterns

Extract characteristic decision-making patterns with cited examples:

```yaml
decision_patterns:
  - pattern: "<named pattern>"
    description: <plain language>
    example:
      context: <the decision>
      reasoning: <how they thought about it>
      source: <cited>
    inverse: <what they would NOT do in that context>
```

Examples of named patterns: "Optimises for irreversibility avoidance", "Prefers small-bet portfolio over big-bet concentration", "Refuses to publish until idea has been steel-manned".

## Behavioral DNA (4-framework score)

Score each framework based on source evidence, NOT speculation. Each scored dimension cites the source.

### DISC profile
- D (Dominance): 0-100 with source evidence
- I (Influence): 0-100 with source evidence
- S (Steadiness): 0-100 with source evidence
- C (Conscientiousness): 0-100 with source evidence
- Type: Dominant pair (D+C, S+C, I+D, etc.)

### Enneagram
- Type: 1-9
- Wing: w-X
- Health level evidence: 1-9 from sources
- Core motivation cited: <source>
- Core fear cited: <source>

### Big Five (OCEAN)
- Openness: 0-100
- Conscientiousness: 0-100
- Extraversion: 0-100
- Agreeableness: 0-100
- Neuroticism: 0-100
Each with 2+ source citations.

### MBTI
- 4 letters with cited preference per letter
- Cognitive function stack derivation

## Callable Advisor YAML (production output)

The final deliverable is a YAML that any /arka command can load:

```yaml
id: <persona-slug>
name: <display name>
canonical_reference: <real human, redacted if confidentiality requires>
expertise_domains_deep: [<list>]
expertise_domains_surface: [<list>]
expertise_domains_nogo: [<list>]
voice_pattern:
  lexical_signature_path: <obsidian link>
  syntactic_signature_path: <obsidian link>
  rhetorical_pattern: <name>
  tonal_signature: <warmth + certainty + humor + confrontation>
beliefs:
  load_bearing: [<list with source IDs>]
  supporting: [<list with source IDs>]
decision_patterns: [<named patterns>]
behavioral_dna:
  disc: { D: X, I: X, S: X, C: X }
  enneagram: { type: X, wing: X }
  big_five: { O: X, C: X, E: X, A: X, N: X }
  mbti: <4 letters>
invocation_examples:
  - context: <when to call this persona>
    expected_output: <what this persona would produce>
```

## Common Failure Modes

1. **Persona without no-go domains** — a persona that opines on everything reads as a generic AI, not a specific human
2. **Beliefs without citations** — single-source claims are not beliefs, they're moments. Drop them
3. **Voice signature copied from prose, not patterns** — describing the voice ("authoritative", "direct") doesn't replicate it. Extract structural N-grams
4. **DNA scored from speculation** — every behavioral score must trace to source evidence
5. **Persona that's actually a category** — "Tech founder" is not a persona, "Paul Graham" is. Personas need a named reference human

## Output → Obsidian: `WizardingCode/Personas/<name>/`

Delivers: source inventory + belief inventory (cited) + voice pattern (4 layers) + expertise map (deep/surface/no-go) + decision patterns + 4-framework DNA + callable advisor YAML + invocation examples.
