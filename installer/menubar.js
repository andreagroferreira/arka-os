/**
 * ArkaOS menu bar launcher wiring (Foundation PR-5).
 *
 * Deploys bin/arka-menubar.py to the purge-proof ~/.arkaos/bin/ (the
 * scheduler-daemon.py pattern — SNAPSHOT_DIRS does not ship bin/, and a
 * launchd unit anchored at an npx cache dies on `npm cache clean`; the
 * PR-1 QG blocker) and manages the io.wizardingcode.arkaos.menubar
 * LaunchAgent.
 *
 * macOS-only by design (rumps is a macOS menu bar framework); every
 * other platform reports { action: "unsupported" } gracefully. Default-on
 * (operator decision, PR-5 Phase 0 — same posture as the PR-1 updater)
 * with a persisted opt-out marker so `npx arkaos menubar disable`
 * survives future updates. ESM, Node + Bun, no interactive prompts.
 * Unit generation (`unitFor`) is pure so it is unit-tested without
 * touching the OS (autoupdate.js precedent).
 */

import { execSync } from "node:child_process";
import {
  chmodSync, copyFileSync, existsSync, mkdirSync, rmSync, writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { getArkaosPython } from "./python-resolver.js";

export const MENUBAR_LABEL = "io.wizardingcode.arkaos.menubar";

function defaultRepoRoot() {
  return join(dirname(fileURLToPath(import.meta.url)), "..");
}

/** Pure: the opt-out marker path — written by disable(), honored by
 *  ensureDefaultEnabled(). */
export function optoutPath(home = homedir()) {
  return join(home, ".arkaos", "menubar.optout");
}

/** Pure: where the menu bar script lives after deployment. */
export function menubarScriptPath(home = homedir()) {
  return join(home, ".arkaos", "bin", "arka-menubar.py");
}

/**
 * Pure: the LaunchAgent plist for the menu bar app. macOS-only — throws
 * on any other platform (callers catch and report "unsupported").
 * KeepAlive is intentionally false: "Quit" must stick until next login;
 * RunAtLoad brings it back at login. LimitLoadToSessionType=Aqua +
 * ProcessType=Interactive mark it as a GUI agent (idiomatic launchd).
 */
export function unitFor(os, { home, pythonPath, scriptPath }) {
  if (os !== "darwin") {
    throw new Error(`menu bar launcher is macOS-only (got ${os})`);
  }
  const log = `${home}/.arkaos/logs/menubar.log`;
  const content = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${MENUBAR_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${pythonPath}</string>
    <string>${scriptPath}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
</dict>
</plist>
`;
  return {
    kind: "launchd",
    files: [
      {
        path: join(home, "Library", "LaunchAgents", `${MENUBAR_LABEL}.plist`),
        content,
      },
    ],
  };
}

/**
 * Copy bin/arka-menubar.py into ~/.arkaos/bin/ (mirrors the
 * scheduler-daemon.py deployment). Returns true when deployed.
 */
export function deployMenubarScript({ repoRoot = defaultRepoRoot(), home = homedir() } = {}) {
  const src = join(repoRoot, "bin", "arka-menubar.py");
  if (!existsSync(src)) return false;
  const dest = menubarScriptPath(home);
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(src, dest);
  try { chmodSync(dest, 0o755); } catch { /* NTFS/ACL no-op */ }
  return true;
}

function _silent(cmd) {
  try {
    execSync(cmd, { stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
}

export function enable({ repoRoot = defaultRepoRoot(), home = homedir() } = {}) {
  if (process.platform !== "darwin") {
    return { ok: false, path: "", message: "Menu bar launcher is macOS-only." };
  }
  if (!deployMenubarScript({ repoRoot, home })) {
    return { ok: false, path: "", message: "bin/arka-menubar.py not found in the package." };
  }
  const pythonPath = getArkaosPython() || "/usr/bin/python3";
  const unit = unitFor(process.platform, {
    home,
    pythonPath,
    scriptPath: menubarScriptPath(home),
  });
  mkdirSync(join(home, ".arkaos", "logs"), { recursive: true });
  for (const f of unit.files) {
    mkdirSync(dirname(f.path), { recursive: true });
    writeFileSync(f.path, f.content, "utf8");
  }
  if (existsSync(optoutPath(home))) rmSync(optoutPath(home));
  const mainPath = unit.files[0].path;
  _silent(`launchctl unload "${mainPath}"`);
  if (!_silent(`launchctl load -w "${mainPath}"`)) {
    return { ok: false, path: mainPath,
      message: "Plist written but launchctl load failed — it will still start at next login." };
  }
  return { ok: true, path: mainPath,
    message: "Menu bar launcher enabled (look for ▲ in the macOS menu bar)." };
}

export function disable({ home = homedir() } = {}) {
  if (process.platform !== "darwin") {
    return { ok: false, path: "", message: "Menu bar launcher is macOS-only." };
  }
  const plist = join(home, "Library", "LaunchAgents", `${MENUBAR_LABEL}.plist`);
  _silent(`launchctl unload "${plist}"`);
  if (existsSync(plist)) rmSync(plist);
  // Persisted opt-out: future `npx arkaos update` runs must not re-enable.
  mkdirSync(join(home, ".arkaos"), { recursive: true });
  writeFileSync(optoutPath(home), new Date().toISOString(), "utf8");
  return { ok: true, path: plist, message: "Menu bar launcher disabled (opt-out persisted)." };
}

export function status({ home = homedir() } = {}) {
  if (process.platform !== "darwin") {
    return { installed: false, supported: false, optout: false,
      message: "menu bar launcher is macOS-only" };
  }
  const plist = join(home, "Library", "LaunchAgents", `${MENUBAR_LABEL}.plist`);
  return {
    installed: existsSync(plist) && existsSync(menubarScriptPath(home)),
    supported: true,
    optout: existsSync(optoutPath(home)),
    kind: "launchd",
    path: plist,
  };
}

/** Default-on wiring for install/update flows: enable unless the user
 *  opted out or the platform is unsupported. Never throws. */
export function ensureDefaultEnabled({ repoRoot = defaultRepoRoot(), home = homedir() } = {}) {
  const s = status({ home });
  if (!s.supported) return { action: "unsupported" };
  if (s.optout) return { action: "optout" };
  if (s.installed) {
    // Refresh script + plist content in place (paths may change between
    // versions) without a reload storm on every update.
    try {
      deployMenubarScript({ repoRoot, home });
      const pythonPath = getArkaosPython() || "/usr/bin/python3";
      const unit = unitFor(process.platform, {
        home, pythonPath, scriptPath: menubarScriptPath(home),
      });
      for (const f of unit.files) writeFileSync(f.path, f.content, "utf8");
    } catch { /* refresh is best-effort */ }
    return { action: "already-enabled" };
  }
  const r = enable({ repoRoot, home });
  return { action: r.ok ? "enabled" : "partial", message: r.message };
}

export async function menubar(args = []) {
  const action = (args[0] || "status").toLowerCase();
  if (action === "enable") {
    const r = enable();
    console.log(`  ${r.ok ? "✓" : "⚠"} ${r.message}${r.path ? `\n    ${r.path}` : ""}`);
  } else if (action === "disable") {
    const r = disable();
    console.log(`  ${r.ok ? "✓" : "⚠"} ${r.message}`);
  } else if (action === "status") {
    const s = status();
    if (!s.supported) console.log(`  Menu bar launcher not supported here: ${s.message}`);
    else if (s.optout) console.log(`  Menu bar: DISABLED by user opt-out\n    (re-enable: npx arkaos menubar enable)`);
    else console.log(`  Menu bar: ${s.installed ? "ENABLED" : "disabled"} (${s.kind})\n    ${s.path}`);
  } else {
    console.error(`  Unknown menubar action: ${action}. Use enable | disable | status.`);
    process.exitCode = 1;
  }
}
