---
name: kb/zettelkasten-process
description: >
  Process content through the Zettelkasten workflow: fleeting → literature → permanent notes.
  Based on Niklas Luhmann's method, modernized by Sönke Ahrens.
allowed-tools: [Read, Write, Edit, Grep, Glob]
---

# Zettelkasten Process — `/kb zettelkasten <note>`

> **Agent:** Helena C. (Knowledge Curator) | **Framework:** Zettelkasten (Luhmann / Ahrens)

## 3 Note Types

### Fleeting Notes
- Quick captures during reading, meetings, or thinking
- Raw, unprocessed, temporary
- Process within 24-48 hours or discard

### Literature Notes
- Summarize source material in YOUR OWN WORDS
- One note per source (book, article, video)
- Include: key ideas, quotes, your reactions
- Always cite source

### Permanent Notes
- One idea per note (atomic)
- Written as if explaining to someone else
- Linked to at least 2 other permanent notes
- Stands alone without context of the source

## Principles

1. **Atomic:** One note = one idea. If you need "and", split it.
2. **Linked:** Every note connects to at least 2 others. Orphan notes are waste.
3. **Emergent:** Structure emerges from links, not pre-defined folders.
4. **Own words:** Never copy-paste. Rephrase forces understanding.
5. **Future self:** Write for someone who doesn't remember the context.

## Process

```
Input (book, article, video, conversation)
  → Fleeting Note (quick capture)
    → Literature Note (summarize in own words)
      → Permanent Note (one atomic idea, linked)
        → MOC update (if cluster grows to 10+ notes)
```

## In Obsidian
- Fleeting: `Inbox/` folder, process during daily review
- Literature: `Sources/` folder with source metadata in frontmatter
- Permanent: Root or topic folders, connected via `[[wikilinks]]`
- MOCs: `Maps/` folder, created when clusters emerge

## Output → Processed notes in Obsidian with links and MOC updates
