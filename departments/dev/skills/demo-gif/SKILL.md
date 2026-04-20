---
name: dev/demo-gif
description: >
  Record a GIF demo of a user flow in the browser. Navigates to a URL,
  executes described interactions, and saves the recording as a GIF file.
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

# Demo GIF Recording — `/dev demo-gif`

> **Agent:** Paulo (Tech Lead) | Requires: Browser integration (`/chrome`)

## Command

```
/dev demo-gif <url> <flow-description>
```

## What It Does

Records a GIF of a user flow in the browser for demos, documentation, or bug reports.

## Workflow

1. **Check browser availability** — follow [Browser Integration Pattern](/arka)
2. **Navigate** to the provided URL
3. **Execute the flow** step by step as described:
   - Parse the flow description into discrete actions (click, type, navigate, scroll)
   - Execute each action with a brief pause between steps for visual clarity
4. **Record** the session as a GIF
5. **Save** the GIF to the current directory with a descriptive filename
6. **Report** file path, file size, and duration

## Example

```
/dev demo-gif http://localhost:3000 "login with test@example.com, navigate to dashboard, create a new project, fill in the name 'My Project', click save"
```

## Fallback (No Browser)

```
⚠ Browser required for demo recording. Enable with: claude --chrome or /chrome
```

## Output

GIF file saved to current working directory: `demo-<timestamp>.gif`
