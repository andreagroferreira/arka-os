---
name: content/research-compile
description: >
  Two-stage sourced research for content production — Madalena researches
  with every claim cited (Agent-Reach, firecrawl/WebSearch fallback,
  [UNVERIFIED] fail-closed), Dinis compiles the production brief the
  scriptwriter consumes (angle, audience, proof, hooks, beats,
  claim→source table). TRIGGER: "/content research <topic>", "pesquisa
  este tema para o vídeo", "research this topic", "faz o research do
  episódio", "production brief", "brief de produção". SKIP: finding WHAT
  to talk about -> content/trend-hunt (this skill assumes the topic);
  library/framework evaluation for code -> dev research; KB-note
  research deliverables -> kb department.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Research Compile — `/content research <topic>`

> **Agents:** Madalena (Content Researcher) → Dinis (Info Compiler) | **Frameworks:** CRAAP + Pyramid Principle

## Stage 1 — Research (Madalena)

1. **KB pass** — vault first; cite `[[wikilinks]]` or declare the gap.
2. **Source sweep** — Agent-Reach primary (YouTube transcripts of the
   best existing pieces, X/Reddit discussion, articles via Jina/Exa),
   firecrawl + WebSearch fallback; declare skipped platforms.
3. **CRAAP filter** — every source rated (currency, relevance,
   authority, accuracy, purpose); weak sources feed context, never
   claims.
4. **Claim ledger** — every factual claim gets a source URL + date.
   Triangulate anything surprising (one source = anecdote, three =
   fact).

**Fail-closed sourcing:** a claim that cannot be verified is either cut
or carried as `[UNVERIFIED]` in bold — it NEVER ships silently as fact.
The scriptwriter and the Quality Gate treat `[UNVERIFIED]` as
do-not-assert-on-camera.

## Stage 2 — Compile (Dinis)

Pyramid Principle: answer first, grouped support below, MECE groups,
nothing missing and nothing extra. The brief is the CONTRACT the script
phase consumes — if the scriptwriter has to re-research, this stage
failed.

## Production brief format (the deliverable)

| Section | Content |
|---|---|
| Angle | one sentence — the take this piece exists to make |
| Audience | who it's for + what they already believe |
| Proof points | ranked, each with its citation |
| Hook material | tensions, numbers, contradictions that earn the click |
| Beat candidates | 5-8 story beats the scriptwriter can structure from |
| Claim → source table | every claim, its URL, its date, its CRAAP grade |
| [UNVERIFIED] ledger | anything carried unverified, and why |

## Output

Production brief to Obsidian
`WizardingCode/Content/Research/<date>-<topic>.md`. Handoff line: ready
for `/content script <topic>` (Joana) or phase 3 of `/content video`.

## Examples

```
/content research "why AI agents fail in production"
/content research "história do FFmpeg"
```
