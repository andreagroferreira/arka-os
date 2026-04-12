# arka-knowledge — ingestion-pipeline

Referenced from SKILL.md. Read only when needed.

## /kb learn <url> [url2 ...] [--persona "Name"]

**This command is NON-BLOCKING.** It queues jobs and returns immediately.

### Step 1: Check Capabilities
```bash
bash <scripts-dir>/kb-check-capabilities.sh
```
Read `~/.arka-os/capabilities.json`. If `yt-dlp` is not available, tell the user to install it and stop. If no transcription method is available, warn the user (download-only mode).

### Step 2: Queue Each URL
For each URL provided, run:
```bash
bash <scripts-dir>/kb-queue.sh "<url>" --persona "<Name>"
```
Returns a job ID (8 chars) immediately. Download + transcription runs in the background.

### Step 3: Display Summary
```
═══ ARKA KB — Jobs Queued ═══
  Job a1b2c3d4 → <url1>
  Job e5f6g7h8 → <url2>
  ...
Transcription: <method>
Media: ~/.arka-os/media/<date>/

Run /kb queue to check progress.
Run /kb process <job-id> when jobs are ready.
═════════════════════════════
```

**IMPORTANT:** Do NOT wait for downloads to complete. Return to the user immediately after queuing.

## /kb process <job-id>

Analyze a ready transcription. This is the INTERACTIVE step that requires Claude Code's LLM.

### Step 1: Validate Job
Read `~/.arka-os/kb-jobs.json`. Find job by ID. Verify status is `ready`.

### Step 2: Read Transcript
Read `<job-output-dir>/audio.txt` for the transcription.
Read `<job-output-dir>/metadata.json` for video title, duration, etc.

### Step 3: Ask User What To Do

Use AskUserQuestion:

1. **Full analysis** — Run all 5 agents, create/update persona + source + topics + MOC pages
2. **Create/update persona only**
3. **Extract frameworks only**
4. **Save transcript to Obsidian only**
5. **Custom analysis**

### Step 4: Update Job Status
Set status to `analyzing` using flock:
```bash
(flock -x 200; jq --arg id "<job-id>" '(.jobs[] | select(.id == $id)).status = "analyzing"' ~/.arka-os/kb-jobs.json > /tmp/kb-tmp.$$.json && mv /tmp/kb-tmp.$$.json ~/.arka-os/kb-jobs.json) 200>~/.arka-os/kb-jobs.lock
```

### Step 5: Execute Analysis (5 parallel agents + DISC)

Launch simultaneously via Task tool:

**Agent 1: Frameworks Extractor** — frameworks, models, methodologies, step-by-step processes, acronyms.

**Agent 2: Strategy Analyzer** — strategies, tactics, specific advice, results/numbers/case studies.

**Agent 3: Voice & Style Profiler** — speaking style (formal/casual), repeated phrases, opening/closing patterns, metaphors.

**Agent 4: Principles Extractor** — core beliefs, what they argue against, driving philosophy.

**Agent 5: Topic Cataloger** — topics covered, relation to existing KB topics, keywords/categories.

**Agent 6: DISC Behavioral Profiler**
- Likely DISC profile from the content
- Pace: fast (D/I) vs deliberate (S/C)
- Focus: tasks/results (D/C) vs people (I/S)
- Handling disagreement: confront=D, persuade=I, avoid=S, analyze=C
- Linguistic patterns: imperative=D, enthusiasm=I, caution=S, data-heavy=C
- Secondary profile + confidence (high/medium/low) with evidence

### Step 6: Write to Obsidian

**Create/Update Persona** — `Personas/<Name>.md`:

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

> [One-line description]

## Voice & Style

[From Agent 3]

## Behavioral Profile (DISC)

> **Primary:** {X} ({name}) | **Secondary:** {Y} ({name}) | **Confidence:** {level}

[From Agent 6]

### Communication Patterns
- **Pace:** {observed}
- **Focus:** {task vs people}
- **Decision speed:** {how they advocate for action}

### How to Create Content as This Persona
- **Tone calibration:** {DISC-based}
- **Opening pattern:** {DISC-informed}
- **Argument structure:** {how they build arguments}
- **Call-to-action style:** {how they close}

### DISC Evidence
- "{quote for primary}"
- "{quote for secondary}"

## Core Philosophy

[From Agent 4]

## Key Frameworks

[From Agent 1]

### Framework: <Name>
- Step 1: ...
- Step 2: ...

## Strategies & Tactics

[From Agent 2]

## Notable Quotes

> "Exact quote"
> "Another memorable phrase"

## Sources

- [[<YYYY-MM-DD> <Video Title>]]

---
*Part of the [[Personas MOC]]*
```

**If existing persona — UPDATE:**
1. Read existing file
2. MERGE new info (don't replace)
3. Add new frameworks, strategies, quotes
4. Add new source link
5. Update `date_updated`
6. Note contradictions if position changed

**Create Source File** — `Sources/Videos/<YYYY-MM-DD> <Video Title>.md`:

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

[Top 5-10 insights]

## Frameworks Found

[List — link to persona]

## Full Analysis

[Combined output from 5 agents]

## Raw Transcript

<details>
<summary>Click to expand full transcript</summary>

[Full transcription text]

</details>

---
*Part of the [[Sources MOC]]*
```

**Catalog by Topic** — `Topics/<Topic Name>.md`:

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

**Update MOC Pages:** `Personas MOC.md`, `Sources MOC.md`, `Topics MOC.md`. Create if absent.

### Step 7: Update Job Status
Set status to `completed` in `~/.arka-os/kb-jobs.json`.

### Step 8: Report
```
═══ ARKA KB — Processing Complete ═══
Job:        <job-id>
Persona:    <Name> (new/updated)
Source:     "<Video Title>" (YouTube)
Duration:   <duration>
Vault:      Personas/<Name>.md
Source:     Sources/Videos/<date> <title>.md
New frameworks found: <count>
New strategies found: <count>
Topics tagged: <list>
Media:      <output-dir>
══════════════════════════════════════
```

## /kb process --all

Process all jobs with status `ready`:
1. Read `~/.arka-os/kb-jobs.json`
2. Filter `status == ready`
3. Run the `/kb process <job-id>` workflow for each
4. Ask once what analysis type to use (or per-job)

## /kb learn-text <file/url> --persona "Name"

Same workflow as `/kb process` full analysis but skip download/transcribe.
- If URL: use WebFetch
- If file: read directly
- Source goes to `Sources/Articles/`
- Synchronous (no background needed)

## /kb write --persona "Name" --type <type>

1. Read `Personas/<Name>.md` for voice and style
2. Read linked source files for frameworks and strategies
3. Generate content in that persona's approach

Supported types: `landing-page`, `email`, `ad`, `social-post`, `blog`, `pitch`, `script`.

With `--personas` (plural) → blend: primary's voice, frameworks from all, annotate origin.

## /kb search <query>

1. Grep across `Personas/`, `Topics/`, `Sources/`
2. Return results organized by relevance
3. Show which personas have insights
4. Include quotes and framework references

## /kb personas

List all files in `Personas/`. Show: name, expertise, source count, last updated.

## /kb topics

List all files in `Topics/`. Show: topic, related personas, last updated.

## /kb cleanup [--older-than 90d]

```bash
bash <scripts-dir>/kb-cleanup.sh --older-than <days>
```
Use `--dry-run` first. Confirm before deletion. Report space freed.
