/**
 * Cross-OS autostart for the ArkaOS dashboard (v3.72.0, feature #2).
 *
 * Opt-in: `npx arkaos autostart enable|disable|status`. Installs a per-OS
 * boot item that runs `scripts/start-dashboard.sh` (macOS/Linux) or
 * `scripts/start-dashboard.ps1` (Windows) — the same launcher the
 * `dashboard` command uses, which already starts the Python API + the
 * dashboard UI (preferring the production build, falling back to dev).
 *
 * ESM, Node + Bun, no interactive prompts. The unit-generation (`unitFor`)
 * is pure so it can be unit-tested without touching the OS.
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const AUTOSTART_LABEL = "io.wizardingcode.arkaos.dashboard";
const SERVICE_NAME = "arkaos-dashboard.service";

function defaultRepoRoot() {
  return join(dirname(fileURLToPath(import.meta.url)), "..");
}

/** Pure: the boot unit for a given platform. Throws on unsupported OS. */
export function unitFor(os, { repoRoot, home }) {
  if (os === "darwin") {
    const startScript = `${repoRoot}/scripts/start-dashboard.sh`;
    const log = `${home}/.arkaos/logs/dashboard-autostart.log`;
    const content = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${AUTOSTART_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${startScript}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ARKAOS_ROOT</key>
    <string>${repoRoot}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
</dict>
</plist>
`;
    return {
      kind: "launchd",
      path: join(home, "Library", "LaunchAgents", `${AUTOSTART_LABEL}.plist`),
      content,
    };
  }

  if (os === "linux") {
    const startScript = `${repoRoot}/scripts/start-dashboard.sh`;
    const content = `[Unit]
Description=ArkaOS Dashboard (Python API + UI)
After=network.target

[Service]
Type=simple
Environment=ARKAOS_ROOT=${repoRoot}
ExecStart=/bin/bash ${startScript}
Restart=on-failure

[Install]
WantedBy=default.target
`;
    return {
      kind: "systemd",
      path: join(home, ".config", "systemd", "user", SERVICE_NAME),
      content,
    };
  }

  if (os === "win32") {
    const ps1 = join(repoRoot, "scripts", "start-dashboard.ps1");
    const content = `@echo off
rem ArkaOS dashboard autostart (login).
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${ps1}"
`;
    return {
      kind: "startup",
      path: join(
        home,
        "AppData", "Roaming", "Microsoft", "Windows",
        "Start Menu", "Programs", "Startup",
        "arkaos-dashboard.cmd",
      ),
      content,
    };
  }

  throw new Error(`unsupported platform for autostart: ${os}`);
}

function _silent(cmd) {
  try {
    execSync(cmd, { stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
}

export function enable({ repoRoot = defaultRepoRoot() } = {}) {
  const unit = unitFor(process.platform, { repoRoot, home: homedir() });
  mkdirSync(dirname(unit.path), { recursive: true });
  mkdirSync(join(homedir(), ".arkaos", "logs"), { recursive: true });
  writeFileSync(unit.path, unit.content, "utf8");
  if (unit.kind === "launchd") {
    _silent(`launchctl unload "${unit.path}"`);
    if (!_silent(`launchctl load -w "${unit.path}"`)) {
      return { ok: false, path: unit.path,
        message: `Plist written but launchctl load failed — it will still run at next login.` };
    }
  } else if (unit.kind === "systemd") {
    _silent("systemctl --user daemon-reload");
    if (!_silent(`systemctl --user enable --now ${SERVICE_NAME}`)) {
      return { ok: false, path: unit.path,
        message: `Service written but systemctl enable failed — check 'systemctl --user' availability.` };
    }
  }
  // startup: writing the .cmd is sufficient; it runs on next login.
  return { ok: true, path: unit.path,
    message: `Autostart enabled (${unit.kind}). The dashboard will start on login.` };
}

export function disable() {
  const unit = unitFor(process.platform, { repoRoot: defaultRepoRoot(), home: homedir() });
  if (unit.kind === "launchd") _silent(`launchctl unload "${unit.path}"`);
  else if (unit.kind === "systemd") _silent(`systemctl --user disable --now ${SERVICE_NAME}`);
  if (existsSync(unit.path)) rmSync(unit.path);
  return { ok: true, path: unit.path, message: "Autostart disabled." };
}

export function status() {
  let unit;
  try {
    unit = unitFor(process.platform, { repoRoot: defaultRepoRoot(), home: homedir() });
  } catch (err) {
    return { installed: false, supported: false, message: err.message };
  }
  return {
    installed: existsSync(unit.path),
    supported: true,
    kind: unit.kind,
    path: unit.path,
  };
}

export async function autostart(args = []) {
  const action = (args[0] || "status").toLowerCase();
  if (action === "enable") {
    const r = enable();
    console.log(`  ${r.ok ? "✓" : "⚠"} ${r.message}\n    ${r.path}`);
  } else if (action === "disable") {
    const r = disable();
    console.log(`  ✓ ${r.message}`);
  } else if (action === "status") {
    const s = status();
    if (!s.supported) console.log(`  Autostart not supported here: ${s.message}`);
    else console.log(`  Autostart: ${s.installed ? "ENABLED" : "disabled"} (${s.kind})\n    ${s.path}`);
  } else {
    console.error(`  Unknown autostart action: ${action}. Use enable | disable | status.`);
    process.exitCode = 1;
  }
}
