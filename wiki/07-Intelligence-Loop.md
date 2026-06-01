# 07 · Intelligence Loop

← [Home](Home.md)

The Intelligence Loop (v2.21.0+) is the wiring that makes ArkaOS consult its
knowledge base before going external, and automatically write every session's
learnings back to the vault. Three independent layers work in sequence on every
prompt and every session end.

The loop compounds daily. Knowledge from today's session is available tomorrow
as injected context. The vault becomes more useful the more it is used.

---

## Architecture

```
Every user prompt
        |
        v
[Layer 1] Synapse L2.5 — KB context injection
        Top 3-5 vault notes injected before the model plans
        |
        v
[Model runs. If it calls an external research tool without having consulted Obsidian first:]
        |
        v
[Layer 2] Research Gate
        First attempt: nudge (allow with advisory)
        Second attempt in same turn: deny
        |
        v
[Session ends. If Quality Gate approved:]
        |
        v
[Layer 3] Auto-Documentor (async)
        Extract -> Classify -> Write -> Relate
        Vault updated before next session starts
```

Each layer is independently disable-able via a feature flag or kill switch.

---

## Layer 1 — Synapse L2.5 KB Context Injection

On every user prompt, Synapse L2.5 runs a semantic search against the Obsidian
vault and injects the top-matching notes as context before the model begins
planning. The agent sees what the vault already knows without being asked to
look.

| Parameter | Value |
|---|---|
| Notes injected | Top 3–5 by similarity score |
| Format | Wikilinks + excerpts in an `[arka:kb-context]` block |
| Fallback | Jaccard similarity when vector store or embedder is absent |
| Feature flag | `synapse.l25KbContext` — default `true` |
| Kill switch | `ARKA_BYPASS_L25=1` |
| Degraded-mode bound | `_MAX_FALLBACK_NOTES = 2000` |

L2.5 sits at priority 25 in the Synapse stack — strictly between L2 (Agent,
priority 20) and L3 (Project, priority 30). It does not block; it informs. The
model is free to ignore the injected notes and go external — which is where
Layer 2 takes over.

---

## Layer 2 — Research Gate

When an agent calls any of the four external research tool families without
having consulted Obsidian this turn, the Research Gate fires.

**Intercepted tools:**
- `mcp__context7__*`
- `WebSearch`
- `WebFetch`
- `mcp__firecrawl__*`

**Behaviour (per turn):**

| Attempt | Gate response |
|---|---|
| First | Allow. Emit `[arka:kb-nudge]` to stderr listing the top 3 vault hits that match the query. |
| Second | Deny. Natural-language explanation in European Portuguese. |

This gradient — natural injection, then nudge, then deny — avoids the friction
of a hard block on every external call while still enforcing the KB-first
discipline over time.

| Parameter | Value |
|---|---|
| Feature flag | `hooks.kbFirst` — default `false` in v2.21.0 (dormant until operator enables) |
| Kill switch | `ARKA_BYPASS_KB_FIRST=1` (usage is audited) |
| Confidence helper | `kb_first_decider.decide_confidence()` — determines whether the vault result is strong enough to skip external lookup |

The gate runs **before** the flow enforcer for these four tool families, so it
does not interfere with Write/Edit/MultiEdit enforcement (governed by
ADR-2026-04-17).

---

## Layer 3 — Auto-Documentor, Cataloger, and Relator

After every approved session, an async worker extracts the session's learnings
and writes them back to the vault. The pipeline has four steps:

```
1. Extract
   Parse the session transcript: sources consulted, decisions made, deliverables produced.

2. Classify (Cataloger)
   Assign the note to one of 8 taxonomic slots:
   - Code pattern       -> Knowledge Base/{stack} Patterns/
   - Persona            -> Personas/{name}/
   - Client strategy    -> Projects/{client}/Strategies/
   - Marketing test     -> Projects/{client}/Campaigns/{campaign}/Tests/
   - Architecture ADR   -> Projects/ArkaOS/ADRs/
   - Research finding   -> Knowledge Base/Research/{topic}/
   - Framework          -> Topics/{framework}/
   - Session learning   -> Knowledge Base/Sessions/{date}/   (fallback)

3. Write
   Create the Obsidian note at the correct vault path with frontmatter and tags.

4. Relate (Relator)
   Find semantically similar existing notes, create bidirectional [[wikilinks]],
   and update the relevant MOCs (Maps of Content).
```

The vault becomes a relational graph. Every session adds nodes and edges.

### Trigger conditions

The auto-documentor fires when all three are true:

1. The session ended via the Stop hook.
2. The Quality Gate returned APPROVED.
3. At least one external tool was called (indicating new information was gathered).

Sessions that were rejected by the Quality Gate do not trigger a write — the
system does not persist rejected work.

### LLM wiring

The synthesis call is runtime-agnostic. No model name is hardcoded.

| Provider | When used | Model decided by |
|---|---|---|
| `subagent` | Default | Active runtime's headless CLI (`claude -p`, `gemini -p …`) |
| `anthropic-direct` | Fallback | `ANTHROPIC_MODEL` env var — no code default |
| `stub` | Tests | Template fallback |

Fallback chain: `subagent → anthropic-direct → stub`. The chain never raises.
Prompt caching is on by default (`cache_control: ephemeral`, 5-min TTL on the
system block).

---

## Budget Telemetry

Every LLM call made by the Intelligence Loop appends a record to
`~/.arkaos/telemetry/llm-cost.jsonl` with tokens used, cache hit rate, and
estimated cost. This is visibility only — it never blocks.

```bash
/arka costs           # today (default)
/arka costs week      # last 7 days
/arka costs month     # last 30 days
/arka costs sessions  # top 10 most expensive sessions
```

A soft advisory appears when a single session exceeds $5 equivalent. There are
no hard caps.

---

## Feature Flags and Kill Switches

| Switch | Effect |
|---|---|
| `synapse.l25KbContext: false` | Disable KB context injection (Layer 1) |
| `ARKA_BYPASS_L25=1` | Same — env var form |
| `hooks.kbFirst: true` | Enable Research Gate enforcement (Layer 2, dormant by default) |
| `ARKA_BYPASS_KB_FIRST=1` | Disable Research Gate; usage is audited |
| `llm.provider: "stub"` | Revert auto-documentor to template synthesiser (Layer 3) |

All three layers are independently toggleable. Disabling one does not affect
the others.

---

## Relationship to the Cognitive Layer

The [Cognitive Layer](06-Cognitive-Layer.md) is the memory substrate: it
defines what to remember (Dreaming, Research, institutional memory) and
provides the vault and vector DB. The Intelligence Loop is the runtime wiring:
it decides when to inject that memory (L2.5) and when and how to write new
learning back (auto-documentor). They depend on each other — the loop without
memory has nothing to inject; memory without the loop does not grow
automatically.

---

Related: [06 · Cognitive Layer](06-Cognitive-Layer.md), [09 · Knowledge Base](09-Knowledge-Base.md), [Home](Home.md)
