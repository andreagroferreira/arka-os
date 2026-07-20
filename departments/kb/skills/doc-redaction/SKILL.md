---
name: kb/doc-redaction
description: >
  Removes sensitive content from documents before they are shared,
  published, or ingested — client identifiers, personal data, secrets,
  internal references — and proves the removal by re-scanning the
  sanitized output, including the places redaction tools miss: metadata,
  embedded text under black boxes, filenames. TRIGGER: "/kb
  doc-redaction", "redact this before sending", "remove os dados do
  cliente deste PDF", "sanitiza este documento", "anonimiza isto antes
  de partilhar", "posso enviar este ficheiro?"; use before any document
  leaves the trust boundary. SKIP: GDPR process/compliance design ->
  ops/gdpr-compliance wins (policy, not one document); extracting data
  from a document -> kb/doc-extraction wins; scrubbing client names
  from generated reports/proposals is already enforced by the platform
  redaction layer — this skill is for source documents.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
metadata:
  origin: arkaos
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Doc Redaction — `/kb doc-redaction`

> **Agent:** Clara (Knowledge Director) | **Framework:** confidentiality mandate, evidence-flow

Redaction is removal, not concealment. A black rectangle drawn over a
name leaves the name in the text layer; a cropped screenshot keeps the
original in the file's history; "find and replace" misses the author
field in the metadata. Every one of those has burned a real
organization, and the difference between them and safe sharing is one
verification pass this skill refuses to skip: the sanitized file is
re-scanned as an adversary would read it, and only what survives that
scan ships.

## Principles

1. **Inventory before removal.** List what counts as sensitive for THIS
   document — client identifiers, people, credentials, internal paths,
   amounts — before touching it. Redaction against an unwritten list is
   guesswork.
2. **Remove, never overlay.** Sensitive content is deleted from the
   content stream, not covered. If the tool draws boxes, the text under
   them must be gone — provably, by extracting the text layer of the
   output.
3. **Metadata is content.** Author fields, tracked changes, comments,
   embedded thumbnails, and the filename itself leak as effectively as
   the body. The sweep covers all of them.
4. **Re-scan as the adversary.** Verification means running extraction
   against the sanitized output — text layer, metadata, search for
   every item on the inventory — and finding nothing. An unverified
   redaction is a promise, not a fact.
5. **Irreversible or it isn't done.** If the original can be recovered
   from the shared artifact (undo history, layers, appended objects),
   the redaction failed regardless of how it looks.

## Process

1. Build the sensitivity inventory for the document (client names,
   PII, secrets, internal references; check `~/.arkaos/redaction-clients.json`
   for the configured client list).
2. Redact by removal in the content stream; regenerate rather than
   annotate when the format makes true removal doubtful.
3. Sweep metadata: document properties, comments, tracked changes,
   embedded objects, filename.
4. Re-scan the output: extract its text layer and metadata, search for
   every inventory item — zero hits or back to step 2.
5. Report what was removed (by category, never by repeating the
   sensitive value) and how the removal was verified.

## Proactive Triggers

Surface these WITHOUT being asked:

- a document about to be shared, attached, or ingested that has not
  been through the inventory+re-scan pass → the risk, and the pass to
  run
- redaction done by visual overlay in a format that keeps text layers →
  the recoverable content underneath
- a "clean" document whose metadata still names people, clients, or
  internal systems → the fields that leak

## Output

```markdown
## Doc Redaction

**Document:** {file, destination/trust boundary}
**Inventory:** {categories identified — never the values}

### Verified
- content: {N removals, by category}
- metadata: {fields swept}
- re-scan: {text layer + metadata + search: zero hits}
- irreversibility: {format-level check}

**Verdict:** {SAFE TO SHARE / BLOCKED — what still leaks, by category}
```
