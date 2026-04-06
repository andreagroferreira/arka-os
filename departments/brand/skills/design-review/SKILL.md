---
name: brand/design-review
description: >
  Open a design tool (Figma, Sketch, Canva desktop) and compare live designs
  against brand guidelines. Screenshot and annotate differences.
  Requires Computer Use (/mcp → computer-use).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Design Review — `/brand design-review`

> **Agent:** Valentina (Creative Director) | Requires: Computer Use (`/mcp` → `computer-use`)

## Command

```
/brand design-review <app-or-file>
```

App can be: Figma, Sketch, Canva, or a direct file path to a design file.

## What It Does

Opens a design tool and compares live designs against brand guidelines. Screenshots and annotates differences.

## Workflow

1. **Check computer-use availability** — follow [Computer Use Availability Check](/arka)
2. **Open** the design tool or file
3. **Navigate** to the relevant artboards/pages
4. **Compare** against brand guidelines:
   - Color palette accuracy (hex values, contrast)
   - Typography (font family, sizes, weights)
   - Spacing and layout consistency
   - Logo usage and clear space
   - Icon style consistency
5. **Screenshot** each artboard with annotations of issues found
6. **Generate report** with side-by-side comparisons

## Example

```
/brand design-review Figma
/brand design-review ~/Documents/Homepage-v3.sketch
/brand design-review "Canva — Social Media Templates"
```

## Fallback (No Computer Use)

```
⚠ Computer Use required for design tool interaction.
Enable via: /mcp → computer-use (macOS only, Pro/Max plan required)
```

## Output

Design review report saved to Obsidian: `Projects/<ecosystem>/Brand/Reviews/<date>.md`
