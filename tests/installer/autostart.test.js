// Tests for the cross-OS autostart unit generation (v3.72.0, feature #2).
//
// Only the pure unit-generation (`unitFor`) is tested — the actual
// launchctl/systemctl/Startup-folder side effects are not exercised here.

import { test } from "node:test";
import assert from "node:assert/strict";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { unitFor, AUTOSTART_LABEL } = await import(
  join(ROOT, "installer", "autostart.js")
);

const ctx = { repoRoot: "/opt/arkaos", home: "/Users/x" };

test("macOS unit is a LaunchAgent plist that runs start-dashboard.sh at load", () => {
  const u = unitFor("darwin", ctx);
  assert.equal(u.kind, "launchd");
  assert.ok(u.path.endsWith(`Library/LaunchAgents/${AUTOSTART_LABEL}.plist`));
  assert.match(u.content, /<key>RunAtLoad<\/key>\s*<true\/>/);
  assert.ok(u.content.includes("/opt/arkaos/scripts/start-dashboard.sh"));
  assert.ok(u.content.includes(AUTOSTART_LABEL));
  assert.ok(u.content.includes("ARKAOS_ROOT"));
});

test("Linux unit is a systemd --user service enabled at default.target", () => {
  const u = unitFor("linux", ctx);
  assert.equal(u.kind, "systemd");
  assert.ok(u.path.endsWith(".config/systemd/user/arkaos-dashboard.service"));
  assert.ok(u.content.includes("WantedBy=default.target"));
  assert.ok(u.content.includes("ExecStart=/bin/bash /opt/arkaos/scripts/start-dashboard.sh"));
  assert.ok(u.content.includes("ARKAOS_ROOT=/opt/arkaos"));
});

test("Windows unit is a Startup-folder .cmd running the PowerShell launcher", () => {
  const u = unitFor("win32", { repoRoot: "C:\\arkaos", home: "C:\\Users\\x" });
  assert.equal(u.kind, "startup");
  assert.ok(u.path.toLowerCase().includes("startup"));
  assert.ok(u.path.endsWith("arkaos-dashboard.cmd"));
  assert.ok(u.content.includes("start-dashboard.ps1"));
});

test("unsupported platform throws", () => {
  assert.throws(() => unitFor("sunos", ctx), /unsupported/i);
});
