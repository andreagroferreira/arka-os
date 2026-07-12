---
name: demo-gif
description: >
  Record a GIF demo of a browser user flow: navigates to a URL, executes the
  described interactions (click, type, scroll) with visual pauses, and saves
  the recording as a GIF for demos, docs, or bug reports. TRIGGER: "demo gif",
  "grava um gif", "record the flow", "gravação do fluxo", "gif para o bug
  report", "/dev demo-gif"; requires browser integration (claude --chrome or
  /chrome). SKIP: native macOS/iOS app walkthroughs -> dev/app-test (Computer
  Use, not browser); writing the docs around the demo -> dev/docs.
---

# Demo GIF Recording

> **Agent:** Paulo (Tech Lead) | Requires: Browser integration (`/chrome`)

## Command

```
/dev demo-gif <url> <flow-description>
```

## What It Does

Records a GIF of a user flow in the browser for demos, documentation, or bug reports.

## Workflow

1. **Check browser availability** — follow Browser Integration Pattern
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
