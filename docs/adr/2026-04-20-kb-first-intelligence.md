---
id: ADR-2026-04-20-kb-first-intelligence
title: KB-First Intelligence Loop — Synapse Injection + Gate + Auto-Documentor
status: accepted
date: 2026-04-20
deciders: Andre Groferreira (owner), Marco (CTO), Marta (CQO), Clara (KB Lead), Paulo (Dev Lead)
related:
  - docs/adr/2026-04-20-flow-marker-v2.md
  - docs/superpowers/specs/2026-04-09-cognitive-layer-design.md
  - core/synapse/layers.py
  - core/synapse/kb_cache.py
  - core/synapse/engine.py
  - core/obsidian/cataloger.py
  - core/obsidian/relator.py
  - core/obsidian/taxonomy.py
  - core/workflow/research_gate.py
  - core/workflow/kb_first_decider.py
  - core/cognition/auto_documentor.py
  - core/jobs/auto_doc_worker.py
  - scripts/migrate_skills_kb_first.py
---

# ADR — KB-First Intelligence Loop

## Status

Accepted — 2026-04-20

## Context

ArkaOS has an Obsidian vault, a vector store, an embedder, and ~250 skills
that describe how to do work. Until this ADR, skills would frequently call
external research tools (mcp__context7__*, WebSearch, WebFetch,
mcp__firecrawl__*) without first consulting the vault. The same research
was repeated across sessions; the vault stagnated; the system did not
compound with use.

Owner's direct framing (PT-PT):

> "ve no seu cérebro nao tem ou tem duvidas vai aprender documenta regista
> e fica mais inteligente. e isso agora nao esta acontecer."

Translated contract:

1. Consult the KB first.
2. If the KB has the answer with confidence, use it.
3. If it has a gap or low confidence, go external, and write the learning
   back into the vault.
4. Tomorrow the vault is smarter than today. The loop compounds.

The core engine pieces were already built (core/knowledge/* embedder +
vector store; core/obsidian/writer.py; core/synapse/kb_cache.py
session cache). What was missing was the *wiring* that made KB-first the
default runtime behaviour.

## Decision drivers

1. KB-first must feel natural, not punitive. A hard "ERROR: consult
   Obsidian first" every time the model tries WebSearch would damage the
   agent's flow. Nudges over denies on first violation.
2. The KB must grow automatically. Manual cataloguing does not scale.
3. Respect the owner's vision of universal cataloguing. Code patterns,
   marketing campaigns, persona insights, architectural decisions — all
   must land in the correct taxonomic home in the vault.
4. No LLM SDK hard dependency for this épico. The auto-documentor must
   work with a template synthesiser today; the LLM call is a plug point
   for a follow-up épico.
5. Rollout safety. Feature flags default off so v2.21.0-beta.1 does not
   break existing sessions.
6. ADR-2026-04-17 invariants untouched. Flow enforcement remains
   authoritative for Write/Edit/MultiEdit; KB-first is a separate,
   orthogonal gate that intercepts external research tools only.

## Alternatives considered

### Alt A — Pure Synapse injection (no gate)

Inject top KB hits into every prompt; trust the model to use them.

- Pros: zero friction, no new enforcement surface.
- Cons: no guarantee the model actually consults the KB before jumping to
  Context7 or WebSearch. Agents with strong "search the web first" priors
  ignore soft hints.
- Rejected as sole solution, kept as the primary mechanism.

### Alt B — Hard gate only (no injection)

PreToolUse blocks external research unless mcp__obsidian__search_notes
was called this turn.

- Pros: strict; forces the behaviour.
- Cons: every external call becomes a round-trip with a deny; terrible
  UX for edge cases.
- Rejected as sole solution.

### Alt C — Synapse injection + safety-net gate + async auto-documentor (adopted)

Layer 1: Synapse L2.5 pre-injects top 3-5 KB hits on every user prompt.
The model sees them before it starts planning.

Layer 2: research_gate PreToolUse gate intercepts the four external
research tool families. First attempt without prior Obsidian consult →
NUDGE (allow with advisory). Second attempt → DENY.

Layer 3: auto_documentor runs async from the Stop hook when Quality
Gate approved. Extracts session learnings, classifies via cataloger,
finds relations via relator, writes back to the correct taxonomic path.

- Pros: gradient UX (natural → nudge → deny); KB grows automatically;
  each layer independently useful and disable-able.
- Cons: more surface area. Acceptable because pieces were already 70% built.
- Adopted.

### Alt D — Full agent with persistent working memory (deferred)

Re-architect the runtime around a memory-augmented agent.

- Pros: correct long-term direction.
- Cons: more than 12 developer-weeks; out of scope for v2.21.0. Revisit in v3.
- Deferred.

## Decision

Adopt Alternative C — Hybrid KB-First Loop. Three layers ship on
feature/intelligence-v2.

### Layer 1 — Synapse L2.5 (core/synapse/layers.py + engine.py)

| Aspect | Value |
|---|---|
| Priority | 25 (strictly between L2=20 and L3=30) |
| Trigger | UserPromptSubmit |
| Output | [arka:kb-context] markdown block with top N notes + wikilinks |
| Feature flag | synapse.l25KbContext; default true |
| Kill switch | ARKA_BYPASS_L25=1 |
| Side effect | Calls kb_cache.record_obsidian_query() |
| Fallback | Jaccard when embedder/vector store absent |

### Layer 2 — Research Gate (core/workflow/research_gate.py)

| Aspect | Value |
|---|---|
| Intercepts | mcp__context7__*, WebSearch, WebFetch, mcp__firecrawl__* |
| Precedence | Runs BEFORE flow_enforcer for these tools |
| First violation | allow=True with [arka:kb-nudge] stderr |
| Second violation | allow=False, PT-PT natural deny |
| Feature flag | hooks.kbFirst; default false in v2.21.0-beta.1 |
| Kill switch | ARKA_BYPASS_KB_FIRST=1 + audit log |
| Confidence helper | kb_first_decider.decide_confidence() |

### Layer 3 — Auto-Documentor (core/cognition/auto_documentor.py + core/jobs/auto_doc_worker.py)

| Aspect | Value |
|---|---|
| Trigger | Stop hook when classifier matched + QG=APPROVED + external tool used |
| Execution | Async worker from ~/.arkaos/jobs/auto-doc/ |
| Pipeline | extract_learnings → choose_model → synthesise → cataloger → relator |
| Model routing | Dynamic (choose_model); no hardcode per domain |
| LLM call | _call_llm hook point; template fallback for v2.21.0 |
| Queue states | pending → processing → completed / failed |
| Retry | 3 attempts before failed |

### Layer 4 — Skills migration (scripts/migrate_skills_kb_first.py)

Idempotent script that injects KB-first prefix into SKILL.md files
that reference external research tools.

| Aspect | Value |
|---|---|
| Scope | arka/**/SKILL.md, departments/**/SKILL.md |
| Delimiter | <!-- arka:kb-first-prefix begin/end --> for idempotency |
| Placement | After frontmatter; else after first # H1 |
| Coverage | 205 of 256 migrated; 51 skipped (no external ref) |

### Taxonomy (core/obsidian/taxonomy.py)

Universal cataloguing across the vault, not a single Auto-captured dump.

| Note type | Vault path template |
|---|---|
| Code pattern | 🧠 Knowledge Base/{stack} Patterns/{title}.md |
| Persona | Personas/{name}/{title}.md |
| Client strategy | Projects/{client}/Strategies/{title}.md |
| Marketing test | Projects/{client}/Campaigns/{campaign}/Tests/{title}.md |
| Architecture decision | Projects/ArkaOS/ADRs/{number}-{slug}.md |
| Research finding | 🧠 Knowledge Base/Research/{topic}/{title}.md |
| Framework | Topics/{framework}/{title}.md |
| Session learning | 🧠 Knowledge Base/Sessions/{date}/{title}.md |

## Rollout

| Milestone | Flag state | Gate |
|---|---|---|
| v2.21.0-beta.1 | l25KbContext=true, kbFirst=false | Full suite green, QG APPROVED |
| Owner dogfooding | as above | Zero false denies in 5 days |
| v2.21.0-beta.2 | kbFirst=true on owner machines | Nudge rate observed |
| v2.21.0 | Both true by default | Two weeks clean telemetry |

Kill switches (ARKA_BYPASS_L25, ARKA_BYPASS_KB_FIRST) remain supported
indefinitely. All bypass usage is audited.

## Consequences

### Positive

- KB becomes a first-class input for every prompt. Repeat research across
  sessions is eliminated by default.
- Approved sessions contribute back automatically — vault compounds.
- Natural UX: the model sees KB context before it plans.
- Four independent layers can be disabled independently.
- Existing vault taxonomy is respected; no forced reorganisation.

### Negative

- Surface area grows by four new Python modules plus one script.
- Template-based synthesiser is a known placeholder; follow-up épico must
  wire real LLM via _call_llm hook point.
- Vault quality depends on cataloger classification accuracy.
- Feature-flag matrix (2 flags x 2 states = 4 configs) widens test surface.

### Neutral

- kb_cache.py now has two responsibilities (session knowledge cache +
  turn-scoped obsidian-query marker). Split if module grows further.

## Test evidence

- tests/python/test_synapse_l25.py — injection, ranking, fallback, flag
- tests/python/test_synapse_kb_cache.py — record/read/invalidate, concurrent
- tests/python/test_research_gate.py — nudge, deny, bypass, traversal
- tests/python/test_kb_first_decider.py — confidence thresholds
- tests/python/test_pre_tool_use_hook.py — end-to-end hook
- tests/python/test_obsidian_taxonomy.py + test_obsidian_cataloger.py +
  test_obsidian_relator.py — catalogue + relate
- tests/python/test_auto_documentor.py + test_auto_doc_worker.py +
  test_stop_hook.py — Stop-to-vault pipeline
- Full suite: 2,858 passing.
- Coverage on new modules: >= 83% each; combined >= 86%.

## References

- Parent plan: ~/.arkaos/plans/2026-04-20-intelligence-v2.md
- Obsidian spec: [[2026-04-20 Intelligence v2 — Flow Marker + KB-First Loop]]
- Cognitive Layer design: docs/superpowers/specs/2026-04-09-cognitive-layer-design.md
- Related ADR (amendment): docs/adr/2026-04-20-flow-marker-v2.md
- Obsidian: [[ArkaOS v2 Architecture Decisions]]
