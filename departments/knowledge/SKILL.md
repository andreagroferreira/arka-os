---
name: kb
description: >
  Dynamic knowledge base system. Downloads YouTube videos, transcribes with Whisper,
  analyzes content, creates/updates personas, catalogs by topic.
  Use when user says "kb", "learn", "persona", "knowledge", or wants to learn from content.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Knowledge Base — ARKA OS Department

Dynamic knowledge acquisition and management system. Learn from YouTube videos, articles, books, and any content source. Build expert personas and a searchable knowledge base.

## Commands

| Command | Description |
|---------|-------------|
| `/kb learn <youtube-url> --persona "Name"` | Download, transcribe, analyze, catalog |
| `/kb learn-text <file/url> --persona "Name"` | Learn from text/article content |
| `/kb persona <name>` | View/manage a persona profile |
| `/kb personas` | List all personas and their stats |
| `/kb search <query>` | Search knowledge base by topic |
| `/kb write --persona "Name" --type <type>` | Generate content using a persona's style |
| `/kb topics` | List all knowledge topics |
| `/kb update <persona> <youtube-url>` | Add more content to existing persona |

## /kb learn <youtube-url> --persona "Name"

### Step 1: Download Audio
```bash
yt-dlp -x --audio-format wav --audio-quality 0 -o "/tmp/arka-kb-%(id)s.%(ext)s" "<url>"
```

### Step 2: Transcribe with Whisper
```bash
whisper "/tmp/arka-kb-<id>.wav" --model medium --language auto --output_format txt --output_dir /tmp/
```

### Step 3: Read Transcription
Read the generated .txt file from /tmp/

### Step 4: Analyze Content (5 parallel agents)

Launch these analysis agents simultaneously:

**Agent 1: Frameworks Extractor**
- What frameworks, models, or methodologies does this person teach?
- What step-by-step processes do they describe?
- What acronyms or named concepts do they use?

**Agent 2: Strategy Analyzer**
- What strategies and tactics are discussed?
- What specific advice is given?
- What results/numbers/case studies are mentioned?

**Agent 3: Voice & Style Profiler**
- How does this person speak? (formal/casual, aggressive/calm)
- What phrases do they repeat?
- What's their opening pattern? Closing pattern?
- What metaphors or analogies do they use?

**Agent 4: Principles Extractor**
- What are the core beliefs expressed?
- What do they argue against?
- What philosophy drives their approach?

**Agent 5: Topic Cataloger**
- What topics does this content cover?
- How does it relate to existing topics in the knowledge base?
- What keywords and categories apply?

### Step 5: Create/Update Persona

Check if `knowledge/personas/<name-slug>/PERSONA.md` exists.

**If new persona:** Create full profile:
```
knowledge/personas/<name-slug>/
├── PERSONA.md          ← Profile (voice, style, principles, how to use)
├── frameworks.md       ← Frameworks and methodologies
├── strategies.md       ← Tactics and advice
├── quotes.md           ← Key phrases and expressions
├── examples.md         ← Case studies and examples
└── sources/
    └── <date>-<video-title>.md  ← Full transcription + analysis
```

**If existing persona:** Update existing files with new information. Merge, don't replace. Note contradictions if the person changed their position.

### Step 6: Catalog by Topic

For each topic identified:
1. Check if `knowledge/topics/<topic-slug>/` exists
2. Create or update `INDEX.md` in that topic directory
3. Link to the persona and specific insights
4. Cross-reference with other personas who speak on the same topic

### Step 7: Update Index

Update `knowledge/INDEX.md` with the new entry.

### Step 8: Cleanup

Remove temporary audio and transcription files from /tmp/.

### Step 9: Report

Display summary:
```
═══ ARKA KB — Learning Complete ═══
Persona:  Sabri Suby (updated)
Source:   "How to Write Ads That Convert" (YouTube)
Duration: 23 min
New frameworks found: 3
New strategies found: 5
Topics tagged: copywriting, facebook-ads, conversion
Persona completeness: 73% (12 videos analyzed)
═══════════════════════════════════
```

## /kb write --persona "Name" --type <type>

Generate content in a persona's style:

1. Read `knowledge/personas/<name>/PERSONA.md` for voice and style
2. Read relevant frameworks and strategies
3. Generate the requested content type using that persona's approach

Supported types: `landing-page`, `email`, `ad`, `social-post`, `blog`, `pitch`, `script`

When `--personas` (plural) is used with multiple names, **blend** the styles:
- Use the primary persona's voice
- Incorporate frameworks from all specified personas
- Note which elements come from which persona

## /kb search <query>

1. Search across all `knowledge/topics/` and `knowledge/personas/` using Grep
2. Return results organized by relevance
3. Show which personas have insights on the query
4. Include specific quotes and framework references
