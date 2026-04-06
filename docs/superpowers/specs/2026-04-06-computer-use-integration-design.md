# Design: Computer Use Integration for ArkaOS

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Skill-Level Integration (mirrors Chrome browser integration pattern)

## Summary

Add Computer Use integration to ArkaOS so department agents can control native apps, click through UIs, type, and screenshot desktop applications. Computer Use is a built-in Claude Code MCP server (`computer-use`) activated via `/mcp`. ArkaOS adds: installer opt-in prompt with restriction warnings, reusable `[COMPUTER]` check pattern, computer-awareness in 5 priority departments, and 2 new computer-only commands.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Installer | Opt-in with restriction warnings (macOS only, Pro/Max) | Transparency upfront avoids frustration |
| Commands | Hybrid — existing gain `[COMPUTER]` steps + 2 new computer-only | Same pattern as Chrome integration |
| Fallback | Informative — skip steps with warning | Consistent with `[BROWSER]` fallback |
| Scope | Top 5 departments | Same as Chrome: `/dev`, `/ecom`, `/brand`, `/ops`, `/strat` |
| Architecture | Skill-level only | Computer Use is managed by Claude Code; ArkaOS tells agents when/how to use it |

## Key Differences from Chrome

| Aspect | Chrome (`[BROWSER]`) | Computer Use (`[COMPUTER]`) |
|--------|---------------------|----------------------------|
| Activation | `--chrome` flag or `/chrome` | `/mcp` → enable `computer-use` |
| Scope | Browser tabs only | Any native macOS app |
| Platform | macOS, Linux, Windows | macOS only |
| Plan | Pro, Max, Team, Enterprise | Pro, Max only |
| Speed | Fast (DOM interaction) | Slower (screenshot + click) |
| Session | Shared browser state | Machine-wide lock, one session at a time |
| Permissions | Site-level via Chrome extension | Per-app approval each session + macOS Accessibility + Screen Recording |

## 1. Installer Computer Use Prompt

**File:** `install.sh` — insert after the Chrome browser integration prompt

```
━━━ Computer Use (Optional) ━━━

Claude Code can control your desktop: open apps, click, type, and screenshot.
Useful for testing native apps, design tools, and GUI-only workflows.
Note: macOS only. Requires Pro or Max plan.

Enable computer use? (y/n): _
```

**If yes:**
1. Write `"computer_use": true` to `~/.arkaos/profile.json`
2. Show instructions:
   ```
   To activate Computer Use:
     1. Run /mcp in a Claude Code session
     2. Find 'computer-use' and select Enable
     3. Grant macOS permissions when prompted (Accessibility + Screen Recording)
     4. You may need to restart Claude Code after granting Screen Recording
   ```

**If no:** Skip. `[COMPUTER]` steps show informative fallback.

## 2. Computer Use Pattern

**File:** `~/.claude/skills/arka/SKILL.md` — new subsection after Browser Integration Pattern

```markdown
### Computer Use Availability Check

When a workflow includes `[COMPUTER]` steps:

1. **Check availability**: Attempt to use a computer-use tool.
   If the computer-use MCP is not enabled, the tool call will fail.

2. **If available**: Execute all `[COMPUTER]` steps normally.
   Note: macOS will prompt for per-app approval on first use each session.

3. **If NOT available**: Skip all `[COMPUTER]` steps and show:

   ```
   ⚠ Computer Use not available — [N] steps were skipped.
   Enable via: /mcp → computer-use (macOS only, Pro/Max plan required)
   Skipped: [list of what was skipped]
   ```

   Then continue with remaining non-computer steps.

4. **Computer-only commands** (`/dev app-test`, `/brand design-review`):
   Show the same warning. No partial fallback (these require GUI control).
```

### Convention

All computer use steps are prefixed with `[COMPUTER]` — consistent with `[BROWSER]` convention.

## 3. Department Computer-Awareness — Existing Commands

### `/dev` — Development (3 skills)

**`departments/dev/skills/code-review/SKILL.md`**
- `[COMPUTER] If native app: launch and click through UI to verify changes visually`

**`departments/dev/skills/tdd-cycle/SKILL.md`**
- `[COMPUTER] If native/mobile app: build, launch, and verify feature in the running app or iOS Simulator`

**`departments/dev/skills/security-audit/SKILL.md`**
- `[COMPUTER] Launch app and test input fields, permissions dialogs, and authentication flows via GUI`

### `/ecom` — E-Commerce (2 skills)

**`departments/ecom/skills/store-audit/SKILL.md`**
- `[COMPUTER] If mobile app: open in iOS Simulator, test purchase flow, verify responsiveness`

**`departments/ecom/skills/analytics/SKILL.md`**
- `[COMPUTER] Open analytics dashboards in native apps (Mixpanel, Amplitude) and verify event tracking`

### `/brand` — Brand & Design (2 skills)

**`departments/brand/skills/identity-system/SKILL.md`**
- `[COMPUTER] Open design tools (Figma, Canva desktop, Sketch) to verify brand assets match guidelines`

**`departments/brand/skills/ux-audit/SKILL.md`**
- `[COMPUTER] Launch the native app, test user flows, screenshot each screen for the audit report`

### `/ops` — Operations (2 skills)

**`departments/ops/skills/workflow-automate/SKILL.md`**
- `[COMPUTER] Open desktop apps (Slack, Notion, calendar apps) to verify automation results`

**`departments/ops/skills/dashboard-build/SKILL.md`**
- `[COMPUTER] Launch dashboard app and verify widgets, charts, and real-time data render correctly`

### `/strat` — Strategy (2 skills)

**`departments/strategy/skills/five-forces/SKILL.md`**
- `[COMPUTER] Open competitor native apps, screenshot UX patterns, extract feature comparisons`

**`departments/strategy/skills/position/SKILL.md`**
- `[COMPUTER] Launch competitor apps side-by-side, compare UI/UX, capture positioning differences`

## 4. New Computer-Only Commands

### `/dev app-test`

**File:** `departments/dev/skills/app-test/SKILL.md` (new)

Build, launch, and click through a native app (macOS or iOS Simulator). Screenshot each screen, report crashes or visual issues.

- Input: build target or app path
- Workflow: build → launch → click through every control/tab → screenshot each state → report
- Fallback: "Computer Use required for native app testing. Enable via /mcp → computer-use"

### `/brand design-review`

**File:** `departments/brand/skills/design-review/SKILL.md` (new)

Open a design tool and compare live designs against brand guidelines. Screenshot and annotate differences.

- Input: app name or file path
- Workflow: open design tool → navigate to artboards → compare against brand guidelines → screenshot differences → generate report
- Fallback: "Computer Use required for design tool interaction. Enable via /mcp → computer-use"

## 5. Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `install.sh` | Modify | Add Computer Use opt-in prompt after Chrome prompt |
| `~/.claude/skills/arka/SKILL.md` | Modify | Add "Computer Use Availability Check" subsection |
| `departments/dev/skills/code-review/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/dev/skills/tdd-cycle/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/dev/skills/security-audit/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/dev/skills/app-test/SKILL.md` | Create | New computer-only native app testing |
| `departments/ecom/skills/store-audit/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/ecom/skills/analytics/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/brand/skills/identity-system/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/brand/skills/ux-audit/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/brand/skills/design-review/SKILL.md` | Create | New computer-only design review |
| `departments/ops/skills/workflow-automate/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/ops/skills/dashboard-build/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/strategy/skills/five-forces/SKILL.md` | Modify | Add `[COMPUTER]` step |
| `departments/strategy/skills/position/SKILL.md` | Modify | Add `[COMPUTER]` step |

**Total:** 2 new files, 13 modifications
