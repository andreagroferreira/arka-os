# ArkaOS Integrations

> Generated from the live `.mcp.json`, `core/knowledge/ingest.py`, and the
> skill tree. External tools change — when one breaks, fix it here and in
> `wiki/18-Integrations-and-Tools.md`.

ArkaOS is not a monolith: it orchestrates external tools and services
through three seams — **MCP servers** (tools with structured schemas),
**CLI tools** (media engines, downloaders, transcriptions), and
**user-local state** (vaults, registries, profiles that never ship in the
repo). This document maps every integration, what it is used for, and
where the code touches it.

## The integration model

| Seam | What it carries | Where it lives |
|---|---|---|
| MCP servers | Structured tools (search, browser, CRM, KB) | `.mcp.json` in the repo root; applied per project |
| CLI tools | Heavy media/compute work (yt-dlp, ffmpeg, Whisper, Higgsfield, Hyperframes) | called by `core/` and `arka/skills/` workflows |
| User-local state | Vaults, memory, registries, keys | `~/.arkaos/`, `~/vault`, `~/.config/opencode` |

Security rule: **secrets never ship in the repo**. API keys are
referenced as `${VAR}` env placeholders in `.mcp.json` and resolved by
the operator's shell environment.

## MCP servers (`.mcp.json`)

Ten servers ship in the root config. They are the structured-tool layer
of every session.

| Server | Purpose | Transport |
|---|---|---|
| `arka-prompts` | ArkaOS department commands — the routing surface | local (`uv run server.py`) |
| `obsidian` | Obsidian vault search/read/write via mcpvault | local (`npx @bitbonsai/mcpvault`) |
| `context7` | Up-to-date library/framework documentation | remote (`@upstash/context7-mcp`) |
| `playwright` | Browser automation (navigate, click, screenshot, network) | local (`@playwright/mcp`) |
| `memory-bank` | Cross-session project memory at `~/memory-bank` | local (`@allpepper/memory-bank-mcp`) |
| `clickup` | Tasks, docs, time tracking, chat (remote MCP) | remote (`mcp.clickup.com`) |
| `firecrawl` | Web search, scrape, crawl, extract, monitors | remote (`firecrawl-mcp`) |
| `sentry` | Error/performance observability | remote HTTP (`mcp.sentry.dev`) |
| `gh-grep` | Real-world code search across public GitHub (grep.app) | remote HTTP (`mcp.grep.app`) |
| `supabase` | Postgres + auth + storage operations | remote HTTP (`mcp.supabase.com`) |

The `clickup`, `firecrawl`, `sentry`, `gh-grep`, and `supabase` servers
are remote and require no local install; the rest run locally via
`npx`/`uv`.

## Media and content generation

Higgsfield and Hyperframes are the two media engines behind the content
department. They are exercised through skills, never hard-coded in core:

- **Higgsfield AI** — image, video, 3D, and audio generation. Skills:
  `content/video-produce` (brief → rendered MP4), `content/image-create`,
  `dev/scroll-world` (scroll-scrubbed cinematic worlds),
  `dev/animated-website` (video → scroll-animated site), plus the
  `higgsfield-*` skill family (generate, soul-id, product-photoshoot,
  marketplace-cards).
- **Hyperframes** — HTML composition framework that renders deterministic
  MP4s. Consumed by `content/video-produce` and the hyperframes skill
  family (`hyperframes-core`, `hyperframes-animation`, `hyperframes-cli`,
  `hyperframes-registry`, `hyperframes-creative`, `hyperframes-keyframes`).
- **`dev/watch`** — downloads video (yt-dlp), extracts scene-aware frames
  (ffmpeg), pulls a timestamped transcript (native captions first, Whisper
  API fallback) so agents can answer questions about video content.
- **`embedded-captions`** — caption/subtitle compositing on existing
  talking-head footage, locally rendered.

## Knowledge pipeline

The KB pipeline (`core/knowledge/ingest.py`) is the ingestion seam. It
auto-detects source type — `youtube`, `pdf`, `audio`, `web`, `markdown` —
and for YouTube runs four phases:

1. **Fetch** — metadata via `yt-dlp` (title, duration, language, thumbnail)
2. **Download** — best video+audio merged to MP4, kept as media
3. **Extract** — WAV audio track via ffmpeg
4. **Transcribe** — `faster-whisper` (recommended) or `openai-whisper`; a
   transcription under 20 characters is treated as a failed ingest

Output is chunked, embedded, and indexed into the local vector store
(`~/.arkaos/knowledge.db`). Missing optional deps degrade loudly
(`RuntimeError` with the exact `pip install` command), never silently.

Sources (PDF, audio, web, markdown) go through the same chunk → embed →
index path. The vault at `~/vault` (Obsidian, via mcpvault) is the
human-readable half; the vector store is the queryable half.

## Graphify knowledge graph

Graphify builds a persistent knowledge graph from a codebase
(`graphify-out/graph.json`) with community detection and query tools.
`arka/SKILL.md` wires it into the KB-first protocol:

1. Query Obsidian first (`mcp__obsidian__search_notes`)
2. When Graphify is configured, also run `mcp__graphify__query_graph`
3. Fall back to the vector KB only after both

Graphify is optional — when not configured, the flow degrades to
Obsidian + vector store without error.

## Research tooling

- **Firecrawl** (MCP) — the general web seam: `search`, `scrape`,
  `crawl`, `extract`, `map`, and async `agent` research jobs with
  `monitor` support for change detection.
- **Context7** (MCP) — developer-doc seam: resolves any library to its
  canonical docs and answers with current API contracts, avoiding stale
  training-data answers.
- **WebSearch / WebReader** — fallback web seams used by skills when
  MCP research servers are unavailable.

## Project and observability

- **ClickUp** (MCP) — tasks, docs, time tracking, chat. The ops/PM
  surface for project state.
- **Sentry** (MCP) — error and performance telemetry.
- **gh-grep / grep.app** (MCP) — search real-world code for patterns
  before implementing unfamiliar APIs.
- **Supabase** (MCP) — database, auth, and storage operations for
  products built on the Supabase stack.
- **memory-bank** (MCP) — per-project cross-session memory.

## Skill → tool matrix

| Skill family | Tool |
|---|---|
| `content/video-produce`, `dev/scroll-world`, `dev/animated-website` | Higgsfield + Hyperframes |
| `content/image-create`, `higgsfield-*` | Higgsfield AI |
| `dev/watch`, `embedded-captions`, KB YouTube ingest | yt-dlp + ffmpeg + Whisper |
| `arka/research`, `kb/*`, `strat/*` research | Firecrawl + Context7 + WebSearch |
| `arka/kb`, KB indexing | Obsidian vault + vector store |
| `ops/*`, `pm/*` task work | ClickUp |
| `dev/security-audit` | Sentry (observability), gh-grep (pattern search) |
| Any codebase work | Graphify (optional) + memory-bank |

## Why `knowledge/ecosystems.json` ships empty

The ecosystem registry is operator-local by design: the repo copy is a
placeholder and the real registry lives at `~/.arkaos/ecosystems.json`.
This keeps per-operator project descriptors and knowledge out of the
repo (confidentiality contract) — `npx arkaos install`/`update` populate
the user-local copy, never the committed one.
