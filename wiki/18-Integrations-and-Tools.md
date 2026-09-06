# 18 · Integrations & Tools

← [Home](Home.md) · [17 · Skill Packs](17-Skill-Packs.md) · [19 · Token Economy](19-Token-Economy.md)

ArkaOS is not a monolith — it orchestrates external tools through three
seams: **MCP servers** (structured tools), **CLI tools** (media engines,
downloaders, transcription), and **user-local state** (vaults, memory,
keys). Full detail: [docs/INTEGRATIONS.md](../docs/INTEGRATIONS.md).

## MCP servers

Ten servers ship in `.mcp.json`; they are the structured-tool layer of
every session. Secrets are `${VAR}` env placeholders, never committed.

| Server | What it gives the agent |
|---|---|
| `arka-prompts` | The department commands — the routing surface |
| `obsidian` | Vault search/read/write (mcpvault at `~/vault`) |
| `context7` | Current library/framework documentation |
| `playwright` | Browser automation — navigate, click, screenshot, network |
| `memory-bank` | Cross-session project memory at `~/memory-bank` |
| `clickup` | Tasks, docs, time tracking, chat |
| `firecrawl` | Web search, scrape, crawl, extract, monitors |
| `sentry` | Error/performance observability |
| `gh-grep` | Real-world code search across public GitHub |
| `supabase` | Postgres, auth, and storage |

Remote servers (clickup, firecrawl, sentry, gh-grep, supabase) need no
local install; the rest run locally via `npx`/`uv`.

## Media engines

- **Higgsfield** — image/video/3D/audio generation behind the content
  department: `content/video-produce`, `content/image-create`,
  `dev/scroll-world`, `dev/animated-website`, and the `higgsfield-*`
  skill family.
- **Hyperframes** — deterministic HTML compositions rendered to MP4:
  `content/hyperframes` (direct work on a project — it loads the
  `/hyperframes` router first), `content/video-produce` (edit/render
  phase) and the `hyperframes-*` family.
- **`dev/watch` + `embedded-captions`** — yt-dlp + ffmpeg + Whisper for
  video analysis and local caption compositing.

## Knowledge pipeline

`core/knowledge/ingest.py` auto-detects `youtube` / `pdf` / `audio` /
`web` / `markdown`. YouTube runs four phases — metadata fetch,
MP4 download, WAV extraction, transcription via `faster-whisper` (or
`openai-whisper`) — then chunk → embed → index into the vector store
(`~/.arkaos/knowledge.db`). The Obsidian vault (`~/vault`) is the
human-readable half; the vector store is the queryable half.

## Graphify knowledge graph

Optional. When configured, `arka/SKILL.md` runs the KB-first protocol:
Obsidian search first, then `graphify__query_graph`, vector KB only as
fallback. Unconfigured Graphify degrades silently.

## Research seams

Firecrawl (search/scrape/crawl/extract/monitor), Context7 (developer
docs), plus WebSearch/WebReader fallbacks when MCP research servers are
unavailable.

## Why `ecosystems.json` ships empty

The real registry lives at `~/.arkaos/ecosystems.json` — per-operator
project descriptors stay out of the repo (confidentiality contract).
`npx arkaos install`/`update` populate the user-local copy.

## Next

[19 · Token Economy](19-Token-Economy.md) — how ArkaOS spends and saves
tokens.
