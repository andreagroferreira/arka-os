---
name: doc-extraction
description: >
  Turns documents — PDFs, scans, images, office exports — into verified
  structured data: chooses text-layer vs OCR per page, extracts tables
  and fields to CSV/JSON/markdown, and validates every extracted value
  against the source before calling it done. TRIGGER: "/kb
  doc-extraction", "extract the tables from this PDF", "OCR this scan",
  "tira os dados desta fatura", "converte este PDF em CSV", "lê este
  documento digitalizado"; use when the input is a document file and the
  output must be data someone can trust. SKIP: extracting from a web
  page or API -> strat/extract-data wins (browser/HTTP, not documents);
  turning a source into study notes for the vault -> kb/learn-content
  wins; removing sensitive content from a document -> kb/doc-redaction
  wins.
metadata:
  origin: arkaos
---

# Doc Extraction

> **Agent:** Clara (Knowledge Director) | **Framework:** evidence-flow, KB-first

A 40-page supplier catalog arrives as a scanned PDF. The text layer is
empty, the tables span page breaks, and one smudged column holds the
prices that will feed an order worth thousands. Run it through a generic
converter and you get plausible numbers — some of them wrong, none of
them flagged. This skill exists for exactly that document: extraction as
an evidence problem, where every value that leaves the file carries the
page it came from and survives a check against the original.

## Principles

1. **Probe before you parse.** Inspect the document first: does it have
   a real text layer, or is it pixels? Text-layer extraction and OCR are
   different tools with different failure modes — choosing blind wastes
   the run.
2. **OCR is a hypothesis, not a fact.** Recognized text is a guess with
   a confidence score. Low-confidence spans get flagged, never silently
   accepted — a wrong digit in a price column is worse than a gap.
3. **Structure survives the page.** Tables that break across pages are
   one table; headers repeat, rows do not. Reassemble before exporting,
   or the output is fragments pretending to be data.
4. **Every value cites its page.** Provenance travels with the data:
   page number and region for each extracted field, so a doubtful value
   can be checked in seconds instead of re-extracting the file.
5. **Validate against the source.** Spot-check extracted values against
   the rendered page — row counts, column sums where they exist, a
   sample of cells read back. Extraction without validation is
   transcription with extra steps.

## Process

1. Inspect the document: page count, text layer present/absent per
   page, image quality, table structure.
2. Choose the path per page: text-layer extraction where it exists, OCR
   where it does not; record which pages took which path.
3. Extract fields and tables; reassemble cross-page structures; carry
   page provenance on every value.
4. Validate: row/column counts vs the source, checksums where the
   document provides totals, spot-read a sample of cells.
5. Export to the requested format (CSV/JSON/markdown) and report
   flagged low-confidence spans honestly — a marked gap beats a silent
   guess.

## Proactive Triggers

Surface these WITHOUT being asked:

- a scanned page with no text layer being read as if it had one → the
  empty extraction it produces, and the OCR path instead
- a table whose totals row disagrees with the sum of extracted values →
  the mismatch, with page reference
- low-confidence OCR spans in fields that feed decisions (prices,
  dates, identifiers) → the flagged values and what confirming them
  requires

## Output

```markdown
## Doc Extraction

**Source:** {file, pages, text-layer/OCR split}
**Extracted:** {tables/fields, format}

### Verified
- structure: {N tables reassembled, cross-page joins}
- validation: {counts/sums checked, sample read-back}
- flagged: {low-confidence spans, with pages}

**Verdict:** {TRUSTED / NEEDS REVIEW — which values and why}
```
