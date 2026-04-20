---
name: strat/extract-data
description: >
  Navigate a web page and extract structured data: tables, lists, prices,
  product listings. Supports CSV, markdown, and JSON output formats.
  Requires browser integration (claude --chrome or /chrome).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Extract Data — `/strat extract-data`

> **Agent:** Tomas (Chief Strategist) | Requires: Browser integration (`/chrome`)

## Command

```
/strat extract-data <url> [format]
```

Formats: `csv` (default), `markdown`, `json`

## What It Does

Navigates a web page and extracts structured data (tables, lists, prices, repeated patterns) into a clean format.

## Workflow

1. **Check browser availability** — follow [Browser Integration Pattern](/arka)
2. **Navigate** to the URL (handles JS-rendered content, pagination, infinite scroll)
3. **Identify structured data** on the page:
   - HTML tables
   - Repeated list patterns (product cards, directory entries)
   - Price/value data
   - Tabular data rendered via JavaScript
4. **Extract** data into structured format
5. **Handle pagination** if detected (ask user: "Found pagination — extract all pages?")
6. **Output** in requested format:
   - CSV: saved to `extracted-<domain>-<timestamp>.csv`
   - Markdown: displayed inline as table
   - JSON: saved to `extracted-<domain>-<timestamp>.json`

## Fallback (No Browser)

```
⚠ Browser not available. Using WebFetch for basic extraction.
For interactive pages (JS-rendered, pagination), enable: /chrome
```

Falls back to WebFetch for static HTML extraction only.

## Output

File saved to current directory or displayed inline (markdown format).
