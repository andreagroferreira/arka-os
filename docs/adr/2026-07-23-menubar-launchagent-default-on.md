# ADR: Menu bar launcher as a default-on LaunchAgent

Date: 2026-07-23
Status: accepted
Related: Foundation PR-5 (#394), follow-ups PR (this change); PR-1 auto-update daemon precedent.

## Context

Foundation PR-5 shipped `bin/arka-menubar.py` — a macOS menu bar app
(rumps) surfacing ArkaOS state (version, sync-pending) and one-click
actions (update check, dashboard, doctor, Start Ollama on local-ai,
auto-update toggle). Something that installs itself into the user's
login session needs its posture documented, not implied.

## Decision

1. **Default-on** (operator decision, PR-5 Phase 0): install/update
   enable the `io.wizardingcode.arkaos.menubar` LaunchAgent on macOS,
   matching the PR-1 auto-update daemon posture. Guards: never on CI,
   never under `--no-system`, and the persisted opt-out marker
   (`~/.arkaos/menubar.optout`) is consulted BEFORE the rumps pip
   install — a user who disabled it pays nothing on updates.
2. **Quit is a pause, disable is permanent and discoverable**:
   `KeepAlive=false` + `RunAtLoad=true` means Quit sticks until next
   login; the menu itself carries "Disable menu bar (permanent)", which
   writes the opt-out marker (same contract as `npx arkaos menubar
   disable`) — and the app's startup guard makes any leftover
   RunAtLoad an instant no-op.
3. **Purge-proof deployment**: the script is copied to
   `~/.arkaos/bin/` (scheduler-daemon pattern) because `SNAPSHOT_DIRS`
   does not ship `bin/` and a unit anchored at the npx cache dies on
   `npm cache clean` (PR-1 QG blocker).
4. **Never a crashing login item**: guarded rumps import, `from
   __future__ import annotations` + a test under the plist's
   last-resort interpreter (`/usr/bin/python3` 3.9), every subprocess
   with a hard timeout, all slow work on daemon worker threads with
   rumps interaction pinned to the AppKit main thread.

## Consequences

- Users get the launcher on their next update with zero setup; the
  opt-out path is one click in the app or one CLI command.
- The doctor `menubar` check probes liveness (`launchctl list`), not
  file presence, so a dead agent cannot read as healthy.
- Linux/Windows are unaffected (`unsupported`, graceful) — a
  cross-platform tray app would be a separate decision.
