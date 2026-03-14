---
name: kb
description: >
  Dynamic knowledge base system powered by Obsidian. Downloads YouTube videos,
  transcribes with Whisper, analyzes content, creates/updates personas in the Obsidian vault.
  Use when user says "kb", "learn", "persona", "knowledge", or wants to learn from content.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Knowledge Base — ARKA OS Department

Dynamic knowledge acquisition and management system. Learn from YouTube videos, articles, books, and any content source. Build expert personas and a searchable knowledge base.

**ALL output goes to the Obsidian vault.**

## Obsidian Configuration

- **Vault:** `/Users/andreagroferreira/Documents/Personal/`
- **Config:** Read `knowledge/obsidian-config.json` for full path/convention details
- **MCP:** Use Obsidian MCP when available, fallback to direct file Write
- **Conventions:** YAML frontmatter, wikilinks `[[]]`, MOC references, kebab-case tags

## Commands

| Command | Description |
|---------|-------------|
| `/kb learn <youtube-url> --persona "Name"` | Download, transcribe, analyze, catalog to Obsidian |
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

### Step 5: Create/Update Persona in Obsidian

Check if `Personas/<Name>.md` exists in the Obsidian vault.

**If new persona — create using this EXACT format** (matching existing Sabri Suby format):

**File:** `Personas/<Name>.md`
```markdown
---
type: persona
name: <Full Name>
expertise:
  - "<primary expertise>"
  - "<secondary expertise>"
date_updated: <YYYY-MM-DD>
tags:
  - "persona"
  - "<expertise-kebab-case>"
---

# <Full Name>

> [One-line description of who they are and what they teach]

## Voice & Style

[From Agent 3 analysis — how they communicate, tone, patterns]

## Core Philosophy

[From Agent 4 analysis — their beliefs and principles]

## Key Frameworks

[From Agent 1 analysis — named frameworks and processes]

### Framework: <Name>
- Step 1: ...
- Step 2: ...

## Strategies & Tactics

[From Agent 2 analysis — actionable advice]

## Notable Quotes

> "Exact quote from content"
> "Another memorable phrase"

## Sources

- [[<YYYY-MM-DD> <Video Title>]]

---
*Part of the [[Personas MOC]]*
```

**If existing persona — UPDATE:**
1. Read the existing persona file
2. MERGE new information (don't replace)
3. Add new frameworks, strategies, quotes
4. Add new source link
5. Update `date_updated` in frontmatter
6. Note contradictions if the person changed their position

### Step 6: Create Source File in Obsidian

**File:** `Sources/Videos/<YYYY-MM-DD> <Video Title>.md`
```markdown
---
type: source
source_type: video
title: "<Video Title>"
url: "<youtube-url>"
persona: "[[<Name>]]"
date_processed: <YYYY-MM-DD>
duration: "<duration>"
tags:
  - "source"
  - "video"
  - "<topic-kebab-case>"
---

# <Video Title>

> Source video for [[<Name>]] persona

## Key Takeaways

[Top 5-10 insights from the video]

## Frameworks Found

[List of frameworks identified — link to persona]

## Full Analysis

[Combined output from all 5 agents]

## Raw Transcript

<details>
<summary>Click to expand full transcript</summary>

[Full transcription text]

</details>

---
*Part of the [[Sources MOC]]*
```

### Step 7: Catalog by Topic in Obsidian

For each topic identified:

**File:** `Topics/<Topic Name>.md` (create or update)
```markdown
---
type: topic
name: <Topic Name>
related_personas:
  - "[[<Name>]]"
date_updated: <YYYY-MM-DD>
tags:
  - "topic"
  - "<topic-kebab-case>"
---

# <Topic Name>

## Perspectives

### [[<Persona Name>]]
[What this persona says about this topic]

---
*Part of the [[Topics MOC]]*
```

### Step 8: Update MOC Pages

Update `Personas MOC.md` to include the new/updated persona link.
Update `Sources MOC.md` to include the new source link.
Update `Topics MOC.md` with any new topics.

Create these MOC files if they don't exist yet.

### Step 9: Cleanup

Remove temporary audio and transcription files from /tmp/.

### Step 10: Report

```
═══ ARKA KB — Learning Complete ═══
Persona:    <Name> (new/updated)
Source:     "<Video Title>" (YouTube)
Duration:   <duration>
Vault:      Personas/<Name>.md
Source:     Sources/Videos/<date> <title>.md
New frameworks found: <count>
New strategies found: <count>
Topics tagged: <list>
═══════════════════════════════════
```

## /kb learn-text <file/url> --persona "Name"

Same workflow as `/kb learn` but skip Steps 1-2 (download/transcribe).
- If URL: use WebFetch to get content
- If file: read directly
- Source goes to `Sources/Articles/` instead of `Sources/Videos/`

## /kb write --persona "Name" --type <type>

Generate content in a persona's style:

1. Read `Personas/<Name>.md` from the Obsidian vault for voice and style
2. Read any linked source files for frameworks and strategies
3. Generate the requested content type using that persona's approach

Supported types: `landing-page`, `email`, `ad`, `social-post`, `blog`, `pitch`, `script`

When `--personas` (plural) is used with multiple names, **blend** the styles:
- Use the primary persona's voice
- Incorporate frameworks from all specified personas
- Note which elements come from which persona

## /kb search <query>

1. Search across `Personas/`, `Topics/`, `Sources/` in the Obsidian vault using Grep
2. Return results organized by relevance
3. Show which personas have insights on the query
4. Include specific quotes and framework references

## /kb personas

List all personas by reading files in `Personas/` directory of the vault.
Show: name, expertise, number of sources, last updated date.

## /kb topics

List all topics by reading files in `Topics/` directory of the vault.
Show: topic name, related personas, last updated date.

## Obsidian Output Paths (Summary)

| Content | Vault Path |
|---------|-----------|
| Personas | `Personas/<Name>.md` |
| Video Sources | `Sources/Videos/<date> <title>.md` |
| Article Sources | `Sources/Articles/<date> <title>.md` |
| Topics | `Topics/<Topic Name>.md` |
| Frameworks | `🧠 Knowledge Base/Frameworks/<name>.md` |
| Raw Transcripts | `🧠 Knowledge Base/Raw Transcripts/<name>.txt` |
| MOC Pages | `Personas MOC.md`, `Topics MOC.md`, `Sources MOC.md` |
