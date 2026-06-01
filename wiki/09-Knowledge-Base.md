# 09 · Knowledge Base

← [Home](Home.md)

ArkaOS's knowledge base is two stores working in tandem: an **Obsidian vault**
for human-readable, navigable notes, and a **vector database** (sqlite-vss)
for semantic retrieval at prompt time. You can write to either directly, or let
the system populate both automatically through the ingestion pipeline and the
auto-documentor.

---

## The two stores

| Store | Technology | What lives there | Who writes |
|---|---|---|---|
| Obsidian vault | Markdown files with frontmatter | Notes, decisions, patterns, strategies, personas | You, agents, auto-documentor |
| Vector DB | sqlite-vss | Chunk embeddings of all indexed content | Ingestion pipeline, auto-documentor |

The stores are kept in sync through indexing. When you run `npx arkaos index`,
the vault is scanned, chunked, embedded, and loaded into sqlite-vss. The
auto-documentor writes to both stores simultaneously after every approved
session.

---

## Ingestion Pipeline

The ingestion pipeline converts external sources into indexed, searchable
knowledge. Four source types are supported: YouTube videos, PDFs, web pages,
and audio files.

```
Source URL or file path
        |
        v
[1. Source detection]
   Identifies type (YouTube / PDF / web / audio)
        |
        v
[2. Download]
   YouTube: yt-dlp extracts audio track
   PDF / web: content fetched directly
   Audio: passed through as-is
        |
        v
[3. Transcribe]
   Whisper generates transcript with timestamps
   (for YouTube and audio; PDFs and web pages use text extraction)
        |
        v
[4. Chunk]
   ~500-token overlapping windows
        |
        v
[5. Embed]
   OpenAI ada-002 (default) or local embedder
        |
        v
[6. Store]
   Vectors written to sqlite-vss with source metadata
        |
        v
[7. Full-text index]
   Updated for hybrid search (semantic + keyword)
        |
        v
Done. Content is retrievable via /arka search and Synapse L2.5.
```

Search combines vector similarity (semantic match) with full-text search
(keyword match) and returns ranked results with relevance scores.

---

## Commands

### Terminal commands

```bash
npx arkaos index           # (Re)index the entire Obsidian vault into the vector store
npx arkaos search <query>  # Semantic search across all indexed content
```

`npx arkaos index` is safe to re-run. It is idempotent — existing chunks are
not duplicated; only new or changed content is processed.

### In-session commands (inside Claude Code / Codex / Gemini / Cursor)

```
/arka index                # Trigger a vault reindex from inside your AI tool
/arka search <query>       # Query the knowledge base and surface relevant notes
```

---

## Vault Taxonomy

The cataloger classifies every auto-documented note into one of eight
taxonomic slots. The path is chosen automatically based on the note's content
and the session context.

| Note type | Vault path |
|---|---|
| Code pattern | `Knowledge Base/{stack} Patterns/{title}.md` |
| Persona | `Personas/{name}/{title}.md` |
| Client strategy | `Projects/{client}/Strategies/{title}.md` |
| Marketing test | `Projects/{client}/Campaigns/{campaign}/Tests/{title}.md` |
| Architecture decision (ADR) | `Projects/ArkaOS/ADRs/{number}-{slug}.md` |
| Research finding | `Knowledge Base/Research/{topic}/{title}.md` |
| Framework | `Topics/{framework}/{title}.md` |
| Session learning (fallback) | `Knowledge Base/Sessions/{date}/{title}.md` |

Notes that don't fit a specific slot fall back to Session learning. Nothing is
dropped.

---

## Personas

A persona is a behavioral and knowledge profile extracted from one or more
sources. It captures how a person thinks, what they prioritize, what language
they use, and what they know — derived from their actual content rather than
synthesized from description.

### Building a persona

Point the ingestion pipeline at the person's sources:

```bash
npx arkaos index --source https://youtube.com/...   # YouTube channel or video
npx arkaos index --source path/to/book.pdf          # Written work
npx arkaos index --source https://example.com/posts # Web content
```

The pipeline downloads, transcribes, chunks, and embeds the content. The
persona builder then synthesizes a behavioral profile from the patterns it
finds.

### Cloning a persona into an agent

Once a persona exists in the vault, it can be cloned into an ArkaOS agent YAML
file. The clone inherits the persona's communication style, frameworks, and
domain knowledge, and receives a standard behavioral DNA profile (DISC,
Enneagram, Big Five, MBTI) derived from the source analysis.

The resulting YAML file is placed at
`departments/{dept}/agents/{persona-slug}.yaml` and is immediately available to
the squad router.

```
/kb persona build          # Build a persona from indexed sources
/kb persona clone          # Convert an existing persona into an agent YAML
```

---

## How Synapse L2.5 uses the vector DB

On every user prompt, Synapse L2.5 queries the vector DB with the prompt text,
retrieves the top 3–5 matching chunks, resolves them back to their source
notes, and injects wikilinks and excerpts as context before the model begins
planning. This is transparent — the model sees what the vault knows without
being asked to search.

When the vector store is absent or the embedder is unavailable, L2.5 falls back
to Jaccard similarity over the note titles, capped at 2,000 notes. Coverage
degrades gracefully; it does not fail.

For the full retrieval mechanics, see [07 · Intelligence Loop](07-Intelligence-Loop.md).

---

## Dashboard

The knowledge base is visible in the ArkaOS dashboard at
`http://localhost:3333/knowledge`. From there you can:

- View all indexed sources with chunk counts and embedding status
- Trigger ingestion for a new source URL
- Monitor background ingestion tasks in real time
- Browse the persona library

Start the dashboard with `npx arkaos dashboard`.

---

## Technical reference

| File | Purpose |
|---|---|
| `core/knowledge/embedder.py` | Generates embeddings (OpenAI ada-002 or local) |
| `core/knowledge/chunker.py` | Splits content into ~500-token overlapping chunks |
| `core/knowledge/vectordb.py` | sqlite-vss storage and hybrid search |
| `core/knowledge/ingest.py` | Full ingestion pipeline (source detection through storage) |
| `core/personas/builder.py` | Persona synthesis from indexed sources |
| `core/personas/cloner.py` | Clone persona into agent YAML |
| `core/obsidian/cataloger.py` | Classifies notes into taxonomy slots |
| `core/obsidian/relator.py` | Creates bidirectional wikilinks and updates MOCs |
| `core/obsidian/taxonomy.py` | Vault path templates per note type |

---

Related: [06 · Cognitive Layer](06-Cognitive-Layer.md), [07 · Intelligence Loop](07-Intelligence-Loop.md), [Home](Home.md)
