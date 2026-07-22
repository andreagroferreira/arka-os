/**
 * Background auto-update daemon for ArkaOS (Foundation PR-1).
 *
 * Users were found running v2 while v4.33 was live — the update path
 * (`npx arkaos@latest update`) only fires when the user remembers to run
 * it. This installs a per-OS scheduled unit that runs
 * `scripts/auto-update.sh` daily (and at load): the script checks the npm
 * registry, applies the core update headlessly, and notifies the user.
 * Project sync stays supervised — the next Claude session picks it up via
 * [arka:update-available].
 *
 * Opt-in by default on install/update (`ensureDefaultEnabled`), with a
 * persisted opt-out marker so `npx arkaos autoupdate disable` survives
 * future updates. ESM, Node + Bun, no interactive prompts. Unit
 * generation (`unitFor`) is pure so it can be unit-tested without
 * touching the OS (autostart.js precedent).
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const AUTOUPDATE_LABEL = "io.wizardingcode.arkaos.updater";
const SERVICE_NAME = "arkaos-updater.service";
const TIMER_NAME = "arkaos-updater.timer";

function defaultRepoRoot() {
  return join(dirname(fileURLToPath(import.meta.url)), "..");
}

/** Pure: the opt-out marker path — written by disable(), honored by
 *  ensureDefaultEnabled() and by scripts/auto-update.sh itself. */
export function optoutPath(home = homedir()) {
  return join(home, ".arkaos", "autoupdate.optout");
}

/** Pure: the scheduled unit(s) for a given platform. Throws on
 *  unsupported OS. Returns { kind, files: [{ path, content }] } —
 *  systemd needs a service + timer pair, launchd a single plist. */
export function unitFor(os, { repoRoot, home }) {
  const script = `${repoRoot}/scripts/auto-update.sh`;
  const log = `${home}/.arkaos/logs/auto-update-daemon.log`;

  if (os === "darwin") {
    // launchd runs with a minimal PATH (/usr/bin:/bin:...) — node/npx
    // live in /opt/homebrew/bin or /usr/local/bin, so the plist must
    // carry a usable PATH or the daemon dies on `command -v npx`.
    // StartCalendarInterval fires daily; RunAtLoad covers machines that
    // were asleep/off at that hour (login catches up).
    const content = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${AUTOUPDATE_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${script}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>10</integer>
    <key>Minute</key>
    <integer>30</integer>
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
      files: [
        {
          path: join(home, "Library", "LaunchAgents", `${AUTOUPDATE_LABEL}.plist`),
          content,
        },
      ],
    };
  }

  if (os === "linux") {
    const service = `[Unit]
Description=ArkaOS auto-update (npm registry watch + headless core update)
After=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash ${script}
StandardOutput=append:${log}
StandardError=append:${log}
`;
    // Persistent=true replays a missed daily run at next boot — the
    // laptop-that-was-off case that left users on v2.
    const timer = `[Unit]
Description=Daily ArkaOS auto-update check

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
`;
    const unitDir = join(home, ".config", "systemd", "user");
    return {
      kind: "systemd",
      files: [
        { path: join(unitDir, SERVICE_NAME), content: service },
        { path: join(unitDir, TIMER_NAME), content: timer },
      ],
    };
  }

  throw new Error(`unsupported platform for autoupdate: ${os}`);
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
  mkdirSync(join(homedir(), ".arkaos", "logs"), { recursive: true });
  for (const f of unit.files) {
    mkdirSync(dirname(f.path), { recursive: true });
    writeFileSync(f.path, f.content, "utf8");
  }
  if (existsSync(optoutPath())) rmSync(optoutPath());
  const mainPath = unit.files[0].path;
  if (unit.kind === "launchd") {
    _silent(`launchctl unload "${mainPath}"`);
    if (!_silent(`launchctl load -w "${mainPath}"`)) {
      return { ok: false, path: mainPath,
        message: "Plist written but launchctl load failed — it will still run at next login." };
    }
  } else if (unit.kind === "systemd") {
    _silent("systemctl --user daemon-reload");
    if (!_silent(`systemctl --user enable --now ${TIMER_NAME}`)) {
      return { ok: false, path: mainPath,
        message: "Timer written but systemctl enable failed — check 'systemctl --user' availability." };
    }
  }
  return { ok: true, path: mainPath,
    message: "Auto-update enabled. ArkaOS checks npm daily and updates itself." };
}

export function disable() {
  const unit = unitFor(process.platform, { repoRoot: defaultRepoRoot(), home: homedir() });
  const mainPath = unit.files[0].path;
  if (unit.kind === "launchd") _silent(`launchctl unload "${mainPath}"`);
  else if (unit.kind === "systemd") _silent(`systemctl --user disable --now ${TIMER_NAME}`);
  for (const f of unit.files) if (existsSync(f.path)) rmSync(f.path);
  // Persisted opt-out: future `npx arkaos update` runs must not re-enable.
  mkdirSync(join(homedir(), ".arkaos"), { recursive: true });
  writeFileSync(optoutPath(), new Date().toISOString(), "utf8");
  return { ok: true, path: mainPath, message: "Auto-update disabled (opt-out persisted)." };
}

export function status() {
  let unit;
  try {
    unit = unitFor(process.platform, { repoRoot: defaultRepoRoot(), home: homedir() });
  } catch (err) {
    return { installed: false, supported: false, optout: false, message: err.message };
  }
  return {
    installed: unit.files.every((f) => existsSync(f.path)),
    supported: true,
    optout: existsSync(optoutPath()),
    kind: unit.kind,
    path: unit.files[0].path,
  };
}

/** Default-on wiring for install/update flows: enable unless the user
 *  opted out or the platform is unsupported. Never throws. */
export function ensureDefaultEnabled({ repoRoot = defaultRepoRoot() } = {}) {
  const s = status();
  if (!s.supported) return { action: "unsupported" };
  if (s.optout) return { action: "optout" };
  if (s.installed) {
    // Refresh unit content in place (paths/schedule may change between
    // versions) but do not force a reload storm on every update.
    try {
      const unit = unitFor(process.platform, { repoRoot, home: homedir() });
      for (const f of unit.files) writeFileSync(f.path, f.content, "utf8");
    } catch {}
    return { action: "already-enabled" };
  }
  const r = enable({ repoRoot });
  return { action: r.ok ? "enabled" : "partial", message: r.message };
}

export async function autoupdate(args = []) {
  const action = (args[0] || "status").toLowerCase();
  if (action === "enable") {
    const r = enable();
    console.log(`  ${r.ok ? "✓" : "⚠"} ${r.message}\n    ${r.path}`);
  } else if (action === "disable") {
    const r = disable();
    console.log(`  ✓ ${r.message}`);
  } else if (action === "run") {
    // Foreground one-shot check — same script the daemon runs.
    const script = join(defaultRepoRoot(), "scripts", "auto-update.sh");
    try {
      execSync(`/bin/bash "${script}" --force`, { stdio: "inherit" });
    } catch { process.exitCode = 1; }
  } else if (action === "status") {
    const s = status();
    if (!s.supported) console.log(`  Auto-update not supported here: ${s.message}`);
    else if (s.optout) console.log(`  Auto-update: DISABLED by user opt-out\n    (re-enable: npx arkaos autoupdate enable)`);
    else console.log(`  Auto-update: ${s.installed ? "ENABLED" : "disabled"} (${s.kind})\n    ${s.path}`);
  } else {
    console.error(`  Unknown autoupdate action: ${action}. Use enable | disable | status | run.`);
    process.exitCode = 1;
  }
}
