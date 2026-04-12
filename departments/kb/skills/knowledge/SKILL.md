---
name: arka-knowledge
description: >
  Dynamic knowledge base powered by Obsidian. Async background processing: queues YouTube
  downloads, transcribes with Whisper (local or API), and pauses for interactive analysis.
  Runs 5 parallel analysis agents (Frameworks, Strategy, Voice & Style, Principles, Topics)
  to build expert personas. Learns from articles and URLs. Creates searchable persona profiles,
  topic cross-references, and source catalogs. Generates content in any learned persona's voice
  and style. All output organized in Obsidian vault with MOC pages.
  Use when user says "kb", "learn", "persona", "knowledge", "youtube", "transcribe", "article",
  "research", "analyze", "source", "topic", "search knowledge", "write as", "queue", "process",
  "capabilities", or wants to learn from any content source or use a persona's expertise.
---

# Knowledge Base — ARKA OS Department

Dynamic knowledge acquisition and management system. Learn from YouTube videos, articles, books, and any content source. Build expert personas and a searchable knowledge base.

**ALL output goes to the Obsidian vault.**

**Background processing:** Downloads and transcriptions run as background jobs. Queue 100 URLs and keep working. Process results interactively when ready.

## Obsidian Configuration

- **Vault:** `/Users/andreagroferreira/Documents/Personal`
- **Config:** Read `knowledge/obsidian-config.json` for full path/convention details
- **MCP:** Use Obsidian MCP when available, fallback to direct file Write
- **Conventions:** YAML frontmatter, wikilinks `[[]]`, MOC references, kebab-case tags

## Commands

| Command | Description |
|---------|-------------|
| `/kb learn <url> [url2 ...] [--persona "Name"]` | Queue download + transcription (async, non-blocking) |
| `/kb learn-text <file/url> --persona "Name"` | Learn from text/article content (synchronous) |
| `/kb queue` | Show all queued/running/ready jobs |
| `/kb status [job-id]` | Detailed status of a specific job |
| `/kb process <job-id>` | Analyze a ready transcription (interactive choices) |
| `/kb process --all` | Process all ready jobs |
| `/kb capabilities` | Show available tools and API keys |
| `/kb cleanup [--older-than 90d]` | Remove old media files |
| `/kb persona <name>` | View/manage a persona profile |
| `/kb personas` | List all personas and their stats |
| `/kb search <query>` | Search knowledge base by topic |
| `/kb write --persona "Name" --type <type>` | Generate content using a persona's style |
| `/kb topics` | List all knowledge topics |
| `/kb update <persona> <youtube-url>` | Add more content to existing persona |

## Scripts Location

All KB scripts are in the `scripts/` subdirectory of this skill:
- `scripts/kb-check-capabilities.sh` — System capability probe
- `scripts/kb-queue.sh` — Queue dispatcher
- `scripts/kb-worker.sh` — Background worker
- `scripts/kb-status.sh` — Status checker
- `scripts/kb-cleanup.sh` — Media cleanup

When installed, scripts live at `~/.claude/skills/arka-knowledge/scripts/`.

## Squad

- **Lead:** Clara (KB department)
- **Specialists:** Persona Analyst, Topic Cataloger, Voice Profiler
- **Quality Gate:** Marta → Eduardo (copy) + Francisca (tech). Mandatory.

## Job Status Flow

```
queued → downloading → transcribing → ready → analyzing → completed
              ↓              ↓
           failed          failed
```

The `ready` → `analyzing` transition happens when user runs `/kb process <job-id>`. Analysis requires Claude Code's LLM (5 parallel agents); cannot run in background bash.

## Obsidian Output Paths

| Content | Vault Path |
|---------|-----------|
| Personas | `Personas/<Name>.md` |
| Video Sources | `Sources/Videos/<date> <title>.md` |
| Article Sources | `Sources/Articles/<date> <title>.md` |
| Topics | `Topics/<Topic Name>.md` |
| Frameworks | `🧠 Knowledge Base/Frameworks/<name>.md` |
| Raw Transcripts | `🧠 Knowledge Base/Raw Transcripts/<name>.txt` |
| MOC Pages | `Personas MOC.md`, `Topics MOC.md`, `Sources MOC.md` |

## References

Read only when needed for the task at hand:

- **Ingestion pipeline** (`/kb learn`, `/kb learn-text`, `/kb process`, `/kb process --all`, `/kb cleanup`, Obsidian page formats, 5+1 analysis agents): `references/ingestion-pipeline.md`
- **Async processing** (`/kb queue`, `/kb status`, `/kb capabilities`, job state file, worker mechanics, media storage, status transitions): `references/async-processing.md`
- **Persona utilities** (`/kb personas`, `/kb persona`, `/kb topics`, `/kb search`, `/kb write`, `/kb update`): `references/ingestion-pipeline.md` (persona output section)
