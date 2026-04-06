---
name: dev/app-test
description: >
  Build, launch, and click through a native app (macOS or iOS Simulator).
  Screenshot each screen, report crashes or visual issues.
  Requires Computer Use (/mcp → computer-use).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# App Test — `/dev app-test`

> **Agent:** Paulo (Tech Lead) | Requires: Computer Use (`/mcp` → `computer-use`)

## Command

```
/dev app-test <target>
```

Target can be: Xcode build target, app bundle path, or iOS Simulator app name.

## What It Does

Builds, launches, and interactively tests a native application by clicking through every control and screen.

## Workflow

1. **Check computer-use availability** — follow [Computer Use Availability Check](/arka)
2. **Build** the target (if source provided): `xcodebuild` or appropriate build command
3. **Launch** the app (or open in iOS Simulator)
4. **Click through** every tab, button, and control systematically
5. **Screenshot** each distinct screen state
6. **Report** findings: crashes, visual glitches, unresponsive controls, layout issues

## Example

```
/dev app-test MenuBarStats
/dev app-test /Applications/MyApp.app
/dev app-test "My iOS App" --simulator
```

## Fallback (No Computer Use)

```
⚠ Computer Use required for native app testing.
Enable via: /mcp → computer-use (macOS only, Pro/Max plan required)
```

## Output

Test report with screenshots and issue list, saved to current directory.
