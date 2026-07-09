---
name: strat/extract-data
description: >
  Navigates a web page via browser integration and extracts structured
  data (tables, lists, prices, product listings) into CSV, markdown, or
  JSON, handling JS-rendered content and pagination, with WebFetch
  fallback for static HTML. TRIGGER: "extrai os dados desta página",
  "scrape this page", "extract the table", "apanha os preços do site",
  "export listings to CSV", "/strat extract-data <url>". SKIP: the ask is
  competitor insight rather than raw data ->
  marketing/competitor-analysis or kb/competitive-intel (they interpret;
  this skill only extracts).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
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
