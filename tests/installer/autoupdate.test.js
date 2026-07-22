// Tests for the auto-update daemon (Foundation PR-1).
//
// Part 1 exercises the pure unit-generation (`unitFor`) — the actual
// launchctl/systemctl side effects are not exercised (autostart.js
// precedent). Part 2 runs scripts/auto-update.sh hermetically: fake
// HOME, PATH-stubbed curl/npx/osascript/notify-send, no network.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync,
  existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { unitFor, optoutPath, AUTOUPDATE_LABEL } = await import(
  join(ROOT, "installer", "autoupdate.js")
);
const SCRIPT = join(ROOT, "scripts", "auto-update.sh");

const ctx = { repoRoot: "/opt/arkaos", home: "/Users/x" };

// ── Part 1: pure unit generation ───────────────────────────────────────

test("macOS unit is a LaunchAgent plist running auto-update.sh daily and at load", () => {
  const u = unitFor("darwin", ctx);
  assert.equal(u.kind, "launchd");
  assert.equal(u.files.length, 1);
  assert.ok(u.files[0].path.endsWith(`Library/LaunchAgents/${AUTOUPDATE_LABEL}.plist`));
  assert.ok(u.files[0].content.includes("/opt/arkaos/scripts/auto-update.sh"));
  assert.match(u.files[0].content, /<key>RunAtLoad<\/key>\s*<true\/>/);
  assert.ok(u.files[0].content.includes("StartCalendarInterval"));
});

test("macOS unit carries a usable PATH (launchd default PATH has no node)", () => {
  const u = unitFor("darwin", ctx);
  assert.match(u.files[0].content, /<key>PATH<\/key>\s*<string>[^<]*homebrew[^<]*<\/string>/);
});

test("Linux unit is a systemd service + persistent daily timer pair", () => {
  const u = unitFor("linux", ctx);
  assert.equal(u.kind, "systemd");
  assert.equal(u.files.length, 2);
  const service = u.files.find((f) => f.path.endsWith("arkaos-updater.service"));
  const timer = u.files.find((f) => f.path.endsWith("arkaos-updater.timer"));
  assert.ok(service.content.includes("ExecStart=/bin/bash /opt/arkaos/scripts/auto-update.sh"));
  assert.ok(timer.content.includes("OnCalendar=daily"));
  // Persistent=true replays a missed run after boot — the laptop-was-off
  // case that left users on v2.
  assert.ok(timer.content.includes("Persistent=true"));
  assert.ok(timer.content.includes("WantedBy=timers.target"));
});

test("unsupported platform throws", () => {
  assert.throws(() => unitFor("sunos", ctx), /unsupported/i);
});

test("opt-out marker lives under ~/.arkaos", () => {
  assert.equal(optoutPath("/Users/x"), "/Users/x/.arkaos/autoupdate.optout");
});

// ── Part 2: hermetic runs of scripts/auto-update.sh ────────────────────

function makeSandbox({ installedVersion, registryVersion, language = "pt", curlFails = false, optout = false }) {
  const home = mkdtempSync(join(tmpdir(), "arka-autoupdate-"));
  const arka = join(home, ".arkaos");
  mkdirSync(arka, { recursive: true });
  writeFileSync(join(arka, "install-manifest.json"), JSON.stringify({ version: installedVersion }));
  writeFileSync(join(arka, "profile.json"), JSON.stringify({ language }));
  if (optout) writeFileSync(join(arka, "autoupdate.optout"), "test");

  const bin = join(home, "stub-bin");
  mkdirSync(bin);
  const stubLog = join(home, "npx-calls.log");
  const notifyLog = join(home, "notify.log");
  const stub = (name, body) => {
    writeFileSync(join(bin, name), `#!/bin/bash\n${body}\n`);
    chmodSync(join(bin, name), 0o755);
  };
  stub("curl", curlFails ? "exit 22" : `echo '{"version":"${registryVersion}"}'`);
  stub("npx", `echo "$@" >> "${stubLog}"; exit 0`);
  stub("osascript", `echo "$@" >> "${notifyLog}"; exit 0`);
  stub("notify-send", `echo "$@" >> "${notifyLog}"; exit 0`);

  return { home, bin, stubLog, notifyLog, log: join(arka, "logs", "auto-update.log") };
}

function runScript(sb, args = []) {
  return spawnSync("/bin/bash", [SCRIPT, ...args], {
    env: { ...process.env, HOME: sb.home, PATH: `${sb.bin}:${process.env.PATH}` },
    encoding: "utf8",
    timeout: 30000,
  });
}

test("newer registry version triggers headless npx update + notification", () => {
  const sb = makeSandbox({ installedVersion: "1.0.0", registryVersion: "9.9.9" });
  const r = runScript(sb);
  assert.equal(r.status, 0);
  assert.ok(readFileSync(sb.stubLog, "utf8").includes("-y arkaos@latest update"));
  const log = readFileSync(sb.log, "utf8");
  assert.ok(log.includes("updating v1.0.0 → v9.9.9"));
  // pt profile → pt-PT notification copy.
  assert.ok(readFileSync(sb.notifyLog, "utf8").includes("9.9.9"));
  rmSync(sb.home, { recursive: true, force: true });
});

test("same version is a no-op (no npx call, 'up to date' logged)", () => {
  const sb = makeSandbox({ installedVersion: "9.9.9", registryVersion: "9.9.9" });
  const r = runScript(sb);
  assert.equal(r.status, 0);
  assert.ok(!existsSync(sb.stubLog));
  assert.ok(readFileSync(sb.log, "utf8").includes("up to date (v9.9.9)"));
  rmSync(sb.home, { recursive: true, force: true });
});

test("--force re-runs the update even when versions match", () => {
  const sb = makeSandbox({ installedVersion: "9.9.9", registryVersion: "9.9.9" });
  const r = runScript(sb, ["--force"]);
  assert.equal(r.status, 0);
  assert.ok(readFileSync(sb.stubLog, "utf8").includes("-y arkaos@latest update"));
  rmSync(sb.home, { recursive: true, force: true });
});

test("user opt-out marker short-circuits before any network call", () => {
  const sb = makeSandbox({ installedVersion: "1.0.0", registryVersion: "9.9.9", optout: true });
  const r = runScript(sb);
  assert.equal(r.status, 0);
  assert.ok(!existsSync(sb.stubLog));
  assert.ok(readFileSync(sb.log, "utf8").includes("opt-out"));
  rmSync(sb.home, { recursive: true, force: true });
});

test("unreachable registry degrades to a logged skip, exit 0", () => {
  const sb = makeSandbox({ installedVersion: "1.0.0", registryVersion: "9.9.9", curlFails: true });
  const r = runScript(sb);
  assert.equal(r.status, 0);
  assert.ok(!existsSync(sb.stubLog));
  assert.ok(readFileSync(sb.log, "utf8").includes("registry unreachable"));
  rmSync(sb.home, { recursive: true, force: true });
});

test("english profile gets english notification copy", () => {
  const sb = makeSandbox({ installedVersion: "1.0.0", registryVersion: "9.9.9", language: "en" });
  runScript(sb);
  assert.ok(readFileSync(sb.notifyLog, "utf8").includes("Updated to v9.9.9"));
  rmSync(sb.home, { recursive: true, force: true });
});
