---
type: spec
status: approved
feature: installer-cross-os
project: ArkaOS
version: 2.24.0
pr: PR2 of 6 (Conclave roadmap 2026-05-13)
branch: feature/v2.24.0-installer-cross-os
date_created: 2026-05-13
tags: [spec, arkaos, installer, cross-os, v2.24.0, conclave-pr2]
---

# SPEC: Installer Cross-OS Completo (v2.24.0)

## Overview

**Problem.** ArkaOS installer is ~65 % cross-OS complete. Obsidian is never auto-installed (only path-detected). Node.js is never validated. `install.sh` hardcodes the GitHub repo URL on line 25 and only scans macOS paths for Obsidian vaults on lines 625–640.

**Goal.** Deliver a full cross-OS install flow (macOS / Linux / Windows) that auto-installs what it can without sudo, reports what needs sudo with copy-paste-ready commands, and falls back gracefully when no package manager is available.

**Actors.** End users running `npx arkaos install` on fresh macOS / Linux / Windows machines; CI pipelines running headless.

## Scope

**In scope (PR2 / v2.24.0):**

| Item | Purpose |
|---|---|
| new `installer/package-manager.js` | brew / winget / snap / apt / choco detection + install helpers |
| new `installer/system-tools.js` | `ensureSystemTools()` phase: Obsidian, Node.js ≥ 20, Python ≥ 3.12 |
| modify `installer/index.js` | call `ensureSystemTools()` before venv creation |
| modify `installer/update.js` | re-run `ensureSystemTools()` on `npx arkaos update` |
| modify `installer/cli.js` | new `npx arkaos doctor` subcommand + `--no-system` flag |
| new `installer/doctor.js` | diagnose-only report (table format, exit codes 0/1/2) |
| modify `install.sh` line 25 | `ARKAOS_REPO_URL` env override (default canonical URL) |
| modify `install.sh` lines 625-640 | add Linux + Windows vault detection |
| modify `installer/index.js` dashboard step | `pnpm install` / `npm ci` in `dashboard/` if Node ≥ 20 |
| new `tests/installer/test_package_manager.mjs` | ≥ 10 Node tests |
| new `tests/installer/test_system_tools.mjs` | ≥ 5 Node tests |

**Out of scope:**

- Auto-update of system tools when newer versions exist (just detect + report).
- Flatpak / AppImage Obsidian variants on Linux (defer to PR6 cleanup if user demand).
- Interactive sudo prompt (André chose "print command for manual run" — headless-safe).
- Aggressive auto-install (André chose hybrid: install what can be installed without sudo; report rest).

## Acceptance Criteria

1. **Fresh macOS install.** Given a Mac without Obsidian, when `npx arkaos install` runs, then `brew install --cask obsidian` is invoked (or printed if brew missing) and Obsidian binary is detected on completion.

2. **Fresh Ubuntu install.** Given Ubuntu without Obsidian / Node, when `npx arkaos install` runs, then the installer prints copy-paste commands like:
   ```
   To finish install, run:
     sudo apt update && sudo apt install -y nodejs
     sudo snap install obsidian --classic
   Then re-run: npx arkaos install
   ```
   and exits with code 0 (informational, not a failure).

3. **Fresh Windows 11.** Given Windows without Obsidian / Node, when `npx arkaos install` runs, then it invokes `winget install --id Obsidian.Obsidian --silent` (and similar for Node), or prints the command if elevation is denied.

4. **`npx arkaos doctor`.** Given any state, when `npx arkaos doctor` runs, then it prints a table with Obsidian / Node / Python rows showing installed/version/location/action, with exit code 0 (all OK), 1 (missing), or 2 (version mismatch).

5. **`install.sh` GitHub URL configurable.** Given `ARKAOS_REPO_URL=https://gitlab.example.com/x/y.git` is set, when `install.sh` runs in curl|bash mode, then it clones from the custom URL.

6. **`install.sh` Linux vault detection.** Given Ubuntu user with vault at `~/.local/share/obsidian/vault` OR `~/Documents/Obsidian`, when `install.sh` runs vault auto-detection, then both candidate paths are scanned.

7. **`install.sh` Windows vault detection.** Given Git Bash on Windows with vault at `$USERPROFILE/Documents/Obsidian`, when `install.sh` runs vault auto-detection, then the path is scanned.

8. **`--no-system` flag.** Given `npx arkaos install --no-system`, when installer runs, then `ensureSystemTools()` is bypassed (legacy install-only flow preserved for CI).

9. **Idempotent.** Given `ensureSystemTools()` has already installed everything, when it runs again, then no install commands fire, no side effects, exit success.

10. **Regression-free.** Given PR2 merges, when full pytest suite runs, then all 3049 tests still pass. New Node tests add ≥ 15 cases for package-manager + system-tools.

11. **shellcheck clean.** Given the updated `install.sh`, when `shellcheck install.sh` runs, then zero new warnings vs baseline.

## Data Model

N/A — pure installer logic, no persisted schema changes.

## API Contracts

### `installer/package-manager.js`

```javascript
/**
 * Detect the highest-priority package manager available on this host.
 *
 * Priority order:
 *   macOS:   brew
 *   Linux:   apt > snap (apt for Node, snap for Obsidian classic-confined)
 *   Windows: winget > choco
 *
 * Returns the canonical name string or null when nothing is available.
 */
export function detectPackageManager(): string | null

/**
 * Install a single package via the detected (or specified) manager.
 * Never invokes sudo automatically. When sudo is required, returns
 * the command for the caller to print and the user to run.
 */
export function installViaPackageManager(
  pkg: string,
  options?: { manager?: string, fallbackUrl?: string }
): {
  success: boolean,
  command: string,           // command that ran or should run
  needsSudo: boolean,
  installed: boolean,        // did we actually install in this call?
  fallbackOpened?: boolean,  // did we open the download URL?
  error?: string,
}

/** Format an array of missing-package commands into copy-paste text. */
export function formatSudoInstructions(missing: SudoCommand[]): string
```

### `installer/system-tools.js`

```javascript
export type ToolStatus = {
  name: "obsidian" | "node" | "python",
  installed: boolean,
  version?: string,
  location?: string,
  needsAction: "none" | "install" | "upgrade",
  suggestedCommand?: string,
  needsSudo?: boolean,
}

/**
 * Check each required system tool. Install what can be installed without
 * sudo. Collect commands for tools that need sudo into `sudoCommands`
 * so the caller can print them to the user.
 *
 * Idempotent: tools already installed at sufficient version are no-ops.
 */
export function ensureSystemTools(options?: {
  skipSystem?: boolean,
  dryRun?: boolean,
}): {
  obsidian: ToolStatus,
  node: ToolStatus,
  python: ToolStatus,
  sudoCommands: string[],
}

export function checkObsidian(): ToolStatus
export function checkNode(): ToolStatus
export function checkPython(): ToolStatus
```

### `installer/doctor.js`

```javascript
/**
 * `npx arkaos doctor` — diagnose-only report. Never installs.
 * Returns exit code 0 (all OK), 1 (missing tool), 2 (version mismatch).
 */
export function runDoctor(): number
```

### CLI integration

`installer/cli.js` gains:
- `npx arkaos doctor` subcommand → calls `runDoctor()`
- `--no-system` global flag → sets `options.skipSystem = true` for `ensureSystemTools()`

## Edge Cases

1. **brew not installed on macOS** → print Homebrew install one-liner, exit 0 with informational message.
2. **snap available but `obsidian` not in store** (older Ubuntu) → fall back to `https://obsidian.md/download` opened in browser, or printed for headless.
3. **Windows < 1809 without winget** → choco fallback, or printed download URL.
4. **Node installed but version < 20** → `needsAction: "upgrade"`, suggested command per OS.
5. **Multiple Python versions present** → prefer 3.12+, recommend `pyenv` if mixed.
6. **User installed Obsidian via Flatpak** → detect via `flatpak list md.obsidian` (best-effort), accept as installed.
7. **Concurrent installer runs** → checks read filesystem only; install commands themselves are idempotent (apt/brew/winget handle already-installed packages gracefully).
8. **curl|bash mode** → `install.sh` clones repo first; `ARKAOS_REPO_URL` env wins over hardcoded default; supports private fork redirection.
9. **Sudo denied** on Windows winget → print the command and ask user to re-run from an elevated prompt; do not loop or retry.
10. **Headless CI** → `--no-system` flag skips entirely; `arka doctor` exit codes drive CI decisions.
11. **Network failure during install** → catch, report, exit with copy-paste recovery command.

## Test Scenarios

| # | Scenario | Type | Expected |
|---|---|---|---|
| 1 | `detectPackageManager` on macOS w/ brew | Unit | `"brew"` |
| 2 | `detectPackageManager` on Ubuntu w/ apt+snap | Unit | `"apt"` (then `"snap"` for Obsidian-specific calls) |
| 3 | `detectPackageManager` on Windows w/ winget | Unit | `"winget"` |
| 4 | `detectPackageManager` on Linux w/ none | Unit | `null` |
| 5 | `checkObsidian` when binary in PATH | Unit | `installed: true, location: <path>` |
| 6 | `checkObsidian` when binary missing | Unit | `installed: false, needsAction: "install"` |
| 7 | `checkNode` when version < 20 | Unit | `needsAction: "upgrade"` |
| 8 | `checkNode` when version ≥ 20 | Unit | `needsAction: "none"` |
| 9 | `checkPython` when 3.11 only | Unit | `needsAction: "upgrade"` |
| 10 | `ensureSystemTools` w/ all 3 missing | Integration | `sudoCommands` array populated |
| 11 | `ensureSystemTools` idempotent | Integration | second call: no commands |
| 12 | `runDoctor` exit codes | Integration | 0 / 1 / 2 verified |
| 13 | `install.sh` with `ARKAOS_REPO_URL` override | Manual / shell | clones from custom URL |
| 14 | `install.sh` Linux vault detection | Manual / shell | finds `~/.local/share/obsidian/...` |
| 15 | `install.sh` Windows vault detection | Manual / shell | finds `$USERPROFILE/Documents/Obsidian` |
| 16 | `--no-system` flag bypass | Integration | `ensureSystemTools` not called |
| 17 | full pytest regression | Integration | 3049 still pass |

## Dependencies

- `installer/platform.js` (existing) — `IS_WINDOWS`, `CMD_FINDER`, `PYTHON_CMD`.
- `installer/path-resolver.js` (PR1) — for any path template substitution.
- `installer/python-resolver.js` (existing) — Python detection logic.
- Node.js `node:child_process` for `execSync` (already used).
- No new npm deps.

## Quality Gate Criteria

- **Eduardo:** all error / status messages read naturally in EN; copy-paste sudo commands are accurate and OS-specific; no AI clichés.
- **Francisca:** package-manager detection covers macOS/Ubuntu/Debian/Fedora/Arch/Windows 10+/11; `ensureSystemTools()` is fully idempotent; no shell injection vectors in execSync calls; shellcheck clean on install.sh.
- **Marta:** verified on 3 synthetic environments — macOS with brew, Ubuntu without snap, Windows with winget — each producing the right printed commands and side effects.

## References

- Plan: `~/.arkaos/plans/2026-05-13-arkaos-next-level-conclave.md` (PR2 section)
- Memory: [[project_next_level_conclave]]
- Existing: [[SPEC-paths-portability]] (PR1, dependency), [[platform.js]] (platform abstraction)
- HIGH items inherited from PR1 audit: `install.sh:25`, `install.sh:625-640`
