---
title: Cognitive Layer pivot — hooks-as-retrieval instead of SQLite/MCP server
date: 2026-05-13
status: accepted
deciders: André (CEO) + Tomas (Strategy) + Marco (CTO) + Marta (CQO)
tags: [adr, cognitive-layer, hooks, retrieval, conclave-pr4, v2.26.0]
---

# ADR — Cognitive Layer: hooks-as-retrieval prototype

## Status

Accepted (2026-05-13 Conclave).

## Context

The cognitive layer is the loop that lets ArkaOS feel *aware* of the user's
ongoing work: it watches what the user does, surfaces relevant prior notes
without being asked, and gets smarter overnight via dreaming/research jobs.

Two architectures were on the table when 2026-04-29 KB note
[[2026-04-29-claude-code-2-1-122-and-2-1-123]] landed:

1. **SQLite SPEC** — a separate process maintains an embeddings index in
   SQLite (sqlite-vec). Workers consult it at each turn. Decision deadline
   for SQLite vs hooks was 2026-05-05 (already passed).
2. **MCP server proper** — a long-running cognitive MCP server registers
   late-bound tools that Claude Code can discover via `ToolSearch`.
3. **Hooks-as-retrieval** — PostToolUse + UserPromptSubmit hooks call a
   small Python helper that searches the Obsidian vault via filesystem
   grep, writes a per-session context cache, and injects an
   `[arka:context]` advisory on the next prompt.

Claude Code 2.1.122 changed two things that affect this:

- `ToolSearch` now picks up MCP tools that connect mid-session
  (late binding), so option 2 is no longer a future-only path.
- Malformed hook entries no longer corrupt `settings.json` — option 3
  becomes safe to ship without the blast-radius risk that previously
  pushed us towards option 1.

## Decision

Adopt **hooks-as-retrieval (option 3) as the v2.26.0 prototype.**
Defer the proper MCP server (option 2) to a later PR (estimated PR7+),
and abandon SQLite SPEC (option 1).

Concretely:

- `core/cognition/retrieval.py` — entity extraction + vault grep + JSON
  cache in `~/.arkaos/context-cache/<session>.json` with 10-minute TTL.
- `config/hooks/post-tool-use.sh` — backgrounded helper call after every
  tool use captures fresh hits into the cache.
- `config/hooks/user-prompt-submit.sh` — reads the cache, formats hits
  as an `[arka:context]` advisory line, and prepends them to
  `additionalContext` on the next turn.
- Hook safety: PostToolUse fires the helper in a backgrounded subshell
  with `disown`, so the 5 s timeout budget is never threatened.
- ripgrep used when available (sub-second across thousands of notes),
  Python fallback capped at 500 files for Windows / minimal Linux installs.

## Rationale

| Criterion | Hooks-as-retrieval (chosen) | SQLite SPEC | MCP server |
| --- | --- | --- | --- |
| Time-to-prototype | 1–2 h | 1–2 weeks | 4–6 h |
| Hook safety blast radius | low (since 2.1.122) | n/a | low |
| Latency added | <800 ms p95 | <50 ms (indexed) | <100 ms (RPC) |
| Operational cost | ripgrep / Python only | sqlite-vec dep + worker | extra long-running process |
| Path to MCP server | trivial — same helper, new transport | requires re-implementing | already there |
| Reversibility | atomic — disable hook line | requires migration | service config |

## Alternatives considered

1. **SQLite SPEC** — Rejected. The 2026-04-29 KB note observed that
   the only remaining advantage over hooks-as-retrieval was *explicit
   retrieval semantics in source-controlled spec form, not capability*.
   The 1–2 week implementation cost is not justified for that delta now
   that hooks are safe.
2. **MCP server proper** — Deferred. The right long-term shape, but the
   v2.26.0 prototype lets us validate the retrieval signal quality
   cheaply before committing to a long-running process.
3. **Synapse L2.5 extension only** — Rejected. Synapse already pre-injects
   top KB matches on user prompts (KB-first protocol). The gap that
   hooks-as-retrieval fills is the *post-tool* signal — the user just
   read a file or ran a command, and we now know far more about what
   they care about than the prompt text alone reveals.

## Consequences

**Positive**

- Cognitive layer ships in this release cycle rather than next quarter.
- Zero new long-running processes — operational footprint unchanged.
- Hooks are atomically reversible (one config line removes the feature).
- Path forward to a proper MCP server is the same code path, swapped
  transport — no rewrite needed.

**Negative**

- Filesystem grep is less semantic than embeddings. We'll miss synonym
  and concept matches a vector store would catch. Accepted for v0.
- Cache is per-session; survives a single conversation. Cross-session
  memory still lives in `auto_documentor` + Dreaming.
- ripgrep is optional but recommended. Python fallback is correct on
  every host; ripgrep just makes it faster on big vaults.

## Validation

- `tests/python/test_retrieval.py` — 20 tests, all green.
- Hook integration verified manually: PostToolUse populates the cache,
  UserPromptSubmit reads it back, advisory appears in next turn's
  `additionalContext` JSON.
- p95 latency budget enforced by `_RIPGREP_TIMEOUT_S=1.0` and
  `_PY_FALLBACK_MAX_FILES=500`.
- Cache TTL (10 min) prevents staleness across long pauses.

## Related

- Plan: `~/.arkaos/plans/2026-05-13-arkaos-next-level-conclave.md` (PR4)
- KB: [[2026-04-29-claude-code-2-1-122-and-2-1-123]] — the unblocking note
- Memory: [[project_next_level_conclave]]
- Future PR: MCP server proper (PR7+, post-roadmap)
