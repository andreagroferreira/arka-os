---
name: knowledge-ops
description: >
  Writes and maintains the Obsidian vault the evidence-first way — a note
  is not "saved" until it is read back, placed in the right department
  path, linked with real `[[wikilinks]]`, and (when indexed) confirmed
  searchable. TRIGGER: "/kb knowledge-ops", "save this to the vault",
  "did the note land", "file this in Obsidian", "guarda isto no vault",
  "confirma que a nota ficou", "indexa isto"; use when capturing or
  reorganising knowledge that must be findable later, not lost. SKIP:
  reading/answering from existing notes -> kb/search-kb wins; turning a
  source (video, PDF, article) into structured notes -> kb/learn-content
  wins; planning a research effort -> kb/research-plan wins.
metadata:
  origin: arkaos
---

# Knowledge Ops

> **Agent:** Clara (Knowledge Director) | **Framework:** Zettelkasten, evidence-flow, KB-first

A note you wrote and a note the vault can give back are different assets,
and the difference is whichever facts quietly failed to land. A file
written to the wrong folder, frontmatter that never parsed, a `[[link]]`
pointing at a note that does not exist, an index that never picked the
note up — each leaves knowledge that *feels* captured but is unfindable
the day it is needed. This skill treats writing to the vault as an
operation to verify, not a fire-and-forget: place it in the right
department path, link it to real neighbours, read it back, and confirm it
is searchable before calling it saved.

## Principles

1. **Search before you write.** Query the vault first — a note that
   duplicates an existing one should extend it, not fork it (KB-first,
   `arka/SKILL.md`).
2. **Right path, valid frontmatter.** File under the correct department
   MOC with parseable YAML frontmatter; a note in the wrong place is a
   note lost.
3. **Links must resolve.** Every `[[wikilink]]` points at a note that
   exists (or is deliberately a forward reference you will create); a
   dead link is a broken trail, not a decoration.
4. **Read it back.** After writing, read the note — confirm the content,
   frontmatter, and links are as intended, not as assumed.
5. **Confirm findable.** When the note must be retrievable, index it and
   verify a search returns it. "Saved" means "the vault can return it."

## Process

1. Search the vault for the topic; decide extend-vs-create.
2. Write or patch the note in the right department path, with frontmatter
   and resolving `[[wikilinks]]`.
3. Read the note back and check content, frontmatter, and every link.
4. If retrieval matters, index and confirm a search surfaces it.
5. Report what landed, where, and how it was verified.

## Proactive Triggers

Surface these WITHOUT being asked:

- a note written with no `[[wikilinks]]` → the orphan it becomes, and the neighbours to link
- a `[[link]]` whose target note does not exist → the dead trail, and whether to create the target or fix the link
- knowledge captured but never indexed when it will be searched for later → the index step that makes it findable

## Output

```markdown
## Knowledge Ops

**Captured:** {what was written / reorganised}
**Location:** {department path + note title}

### Verified
- frontmatter: {parsed OK}
- links: {N wikilinks, all resolve}
- read-back: {confirmed}
- searchable: {index confirmed / n/a}

**Verdict:** {SAVED and findable / INCOMPLETE — what still needs fixing}
```
