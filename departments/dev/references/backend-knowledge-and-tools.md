# Backend Knowledge & Tools — Squad Reference

> Shared reference for the dev backend sub-squads. Read this before any
> backend work. It defines the KB-first rule, the per-stack knowledge
> sources, the live-doc grounding, and the sub-squad structure.

---

## 1. KB-First + Live Grounding (NON-NEGOTIABLE)

**The Obsidian knowledge base is the canonical, primary source.** For
fast-moving frameworks (especially Laravel), supplement the KB with **live
doc grounding** so answers are always current — never answer from memory.

Order of operations on ANY backend task:

1. **Search the Obsidian KB first** for the relevant stack + project patterns.
2. **Cite** with `[[wikilinks]]` or declare a KB gap.
3. **Ground against live docs** for the framework in use:
   - Laravel → **laravel-boost MCP** + **context7**
   - Python / Node-TS → **context7**
   - then nuxt-ui/next-devtools/etc. as the framework dictates.
4. When live research produces something material, **write it back to the
   KB** so the vault gets richer over time (this feeds the daily reorganizer).

This mirrors the `kb-first` constitution rule and the Synapse L2.5 layer.

---

## 2. Per-Stack Knowledge Sources

| Stack | KB sources (Obsidian) | Live grounding |
|---|---|---|
| Laravel | `[[Area 08 - Desenvolvimento de Alta Performance]]`, `[[Backend - Clean Code e Padroes Laravel]]`, project audits | laravel-boost MCP + context7 |
| Python | Area 08 + project notes | context7 |
| Node/TS | Area 08 + project notes | context7 |
| Data/ETL | project data-model notes | context7 |
| AI/RAG | cognitive-layer notes, MCP notes | context7 |

> The dedicated per-stack KB areas land in **PR-2** (knowledge-wiring), where
> the Dreaming → reorganizer pipeline feeds each specialist daily.

---

## 3. Sub-Squad Structure

```
dev → Backend Core      Andre (lead) · Gonçalo (Laravel) · Diogo (Python) · Vera (Node/TS)
dev → Data Platform     Vasco (lead) · Duarte (ETL)
dev → AI Engineering    Salvador (RAG / agents / MCP)
dev (cross-cutting)     Gabriel (architect) — DDD, event storming, bounded contexts, patterns
```

**Routing rule:** the Backend Core lead (Andre) routes language-specific work
to the right specialist — Laravel → Gonçalo, Python → Diogo, Node/TS → Vera.
Data/pipeline work → Vasco/Duarte. AI/RAG/MCP/agent flows → Salvador. Domain
design / patterns / ADRs → Gabriel. Specialists escalate to their sub-squad
lead; leads escalate to Paulo (tech-lead).

---

## 4. Standards (NON-NEGOTIABLE, per CLAUDE.md)

- **Laravel:** Services + Repositories, Form Requests, API Resources, Feature
  Tests (Pest). No business logic in controllers, no raw SQL in the app layer.
- **Python:** type hints everywhere, Pydantic, virtual envs (uv/poetry).
- **Node/TS:** strict TypeScript, contract-first (Zod/OpenAPI), no `any`.
- **SOLID + Clean Code** (non-negotiable): SRP, functions < 30 lines, max 3
  nesting, self-documenting names, no dead code.
- **Git:** conventional commits, feature branches.
