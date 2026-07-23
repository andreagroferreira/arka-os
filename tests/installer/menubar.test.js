// Foundation PR-5 — menu bar launcher.
//
// Part 1 exercises the pure unit-generation and deployment paths — the
// launchctl side effects are never exercised (autoupdate.js precedent).
// Part 2 runs the PURE Python state/menu model hermetically via the
// --print-state/--print-menu introspection flags with a sandboxed
// ARKA_MENUBAR_HOME — rumps is never imported (no display, no macOS
// dependency in the suite).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync,
  existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  MENUBAR_LABEL, deployMenubarScript, menubarScriptPath, optoutPath, unitFor,
} = await import(join(ROOT, "installer", "menubar.js"));
const MENUBAR_PY = join(ROOT, "bin", "arka-menubar.py");

const HAVE_PY = (() => {
  try {
    return spawnSync("python3", ["--version"], { stdio: "ignore" }).status === 0;
  } catch {
    return false;
  }
})();

const ctx = {
  home: "/Users/x",
  pythonPath: "/Users/x/.arkaos/venv/bin/python",
  scriptPath: "/Users/x/.arkaos/bin/arka-menubar.py",
};

// ── Part 1: pure unit generation + deployment ──────────────────────────

test("macOS unit is a LaunchAgent plist running the deployed script at login", () => {
  const u = unitFor("darwin", ctx);
  assert.equal(u.kind, "launchd");
  assert.equal(u.files.length, 1);
  assert.ok(u.files[0].path.endsWith(`Library/LaunchAgents/${MENUBAR_LABEL}.plist`));
  assert.ok(u.files[0].content.includes(ctx.pythonPath));
  assert.ok(u.files[0].content.includes(ctx.scriptPath));
  assert.match(u.files[0].content, /<key>RunAtLoad<\/key>\s*<true\/>/);
  // Quit must stick until next login — KeepAlive would resurrect the app.
  assert.match(u.files[0].content, /<key>KeepAlive<\/key>\s*<false\/>/);
});

test("unit carries a usable PATH (menu actions shell out to npx/ollama)", () => {
  const u = unitFor("darwin", ctx);
  assert.match(u.files[0].content, /<key>PATH<\/key>\s*<string>[^<]*homebrew[^<]*<\/string>/);
});

test("non-macOS platforms throw (callers report unsupported)", () => {
  for (const os of ["linux", "win32", "sunos"]) {
    assert.throws(() => unitFor(os, ctx), /macOS-only/);
  }
});

test("opt-out marker and script path live under ~/.arkaos", () => {
  assert.equal(optoutPath("/Users/x"), "/Users/x/.arkaos/menubar.optout");
  assert.equal(menubarScriptPath("/Users/x"), "/Users/x/.arkaos/bin/arka-menubar.py");
});

test("deployMenubarScript copies bin/arka-menubar.py to ~/.arkaos/bin, executable", () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "arka-menubar-repo-"));
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-home-"));
  try {
    mkdirSync(join(repoRoot, "bin"), { recursive: true });
    writeFileSync(join(repoRoot, "bin", "arka-menubar.py"), "#!/usr/bin/env python3\n");
    assert.equal(deployMenubarScript({ repoRoot, home }), true);
    const dest = menubarScriptPath(home);
    assert.ok(existsSync(dest));
    assert.equal(readFileSync(dest, "utf8"), "#!/usr/bin/env python3\n");
    if (process.platform !== "win32") {
      assert.ok(statSync(dest).mode & 0o100, "deployed script must be executable");
    }
  } finally {
    rmSync(repoRoot, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

test("deployMenubarScript degrades to false when the source is missing", () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "arka-menubar-empty-"));
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-home2-"));
  try {
    assert.equal(deployMenubarScript({ repoRoot, home }), false);
    assert.ok(!existsSync(menubarScriptPath(home)));
  } finally {
    rmSync(repoRoot, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

// ── Part 2: hermetic Python state/menu model ───────────────────────────

function pyProbe(flag, { files = {}, ollama = "" } = {}) {
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-py-"));
  const arka = join(home, ".arkaos");
  mkdirSync(arka, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    writeFileSync(join(arka, name), body);
  }
  const run = spawnSync("python3", [MENUBAR_PY, flag], {
    env: {
      ...process.env,
      ARKA_MENUBAR_HOME: home,
      ...(ollama ? { ARKA_MENUBAR_OLLAMA: ollama } : {}),
    },
    encoding: "utf8",
    timeout: 15000,
  });
  rmSync(home, { recursive: true, force: true });
  assert.equal(run.status, 0, `stderr: ${run.stderr}`);
  return JSON.parse(run.stdout);
}

test("state: reads version, sync-pending, profile, autoupdate opt-out", { skip: !HAVE_PY }, () => {
  const state = pyProbe("--print-state", {
    files: {
      "install-manifest.json": JSON.stringify({ version: "9.9.9" }),
      "sync-state.json": JSON.stringify({ version: "pending-sync" }),
      "profile.json": JSON.stringify({ installProfile: "local-ai" }),
      "autoupdate.optout": "2026-07-23",
    },
  });
  assert.equal(state.version, "9.9.9");
  assert.equal(state.sync_pending, true);
  assert.equal(state.profile, "local-ai");
  assert.equal(state.autoupdate_on, false);
});

test("state: empty home degrades to safe defaults, exit 0", { skip: !HAVE_PY }, () => {
  const state = pyProbe("--print-state");
  assert.equal(state.version, null);
  assert.equal(state.sync_pending, false);
  assert.equal(state.profile, "essential");
  assert.equal(state.autoupdate_on, true);
});

test("state: invalid installProfile degrades to essential", { skip: !HAVE_PY }, () => {
  const state = pyProbe("--print-state", {
    files: { "profile.json": JSON.stringify({ installProfile: "yolo" }) },
  });
  assert.equal(state.profile, "essential");
});

test("menu: Start Ollama appears ONLY on local-ai with ollama stopped", { skip: !HAVE_PY }, () => {
  const localStopped = pyProbe("--print-menu", {
    files: { "profile.json": JSON.stringify({ installProfile: "local-ai" }) },
    ollama: "stopped",
  });
  assert.ok(localStopped.includes("start_ollama"));

  const localRunning = pyProbe("--print-menu", {
    files: { "profile.json": JSON.stringify({ installProfile: "local-ai" }) },
    ollama: "running",
  });
  assert.ok(!localRunning.includes("start_ollama"));

  const essentialStopped = pyProbe("--print-menu", {
    files: { "profile.json": JSON.stringify({ installProfile: "essential" }) },
    ollama: "stopped",
  });
  assert.ok(!essentialStopped.includes("start_ollama"));
});

test("menu: core actions always present, quit last", { skip: !HAVE_PY }, () => {
  const items = pyProbe("--print-menu", { ollama: "absent" });
  for (const id of ["check_updates", "open_dashboard", "doctor", "autoupdate_toggle"]) {
    assert.ok(items.includes(id), `missing ${id}`);
  }
  assert.equal(items[items.length - 1], "quit");
});
