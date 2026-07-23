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
  chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync,
  writeFileSync, existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  MENUBAR_LABEL, deployMenubarScript, ensureDefaultEnabled, menubarHealthy,
  menubarScriptPath, optoutPath, unitFor, xmlEscape,
} = await import(join(ROOT, "installer", "menubar.js"));
const { optoutPath: autoupdateOptoutPath } = await import(
  join(ROOT, "installer", "autoupdate.js")
);
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
  // GUI LaunchAgent idiom: Aqua session only, interactive process class.
  assert.match(u.files[0].content, /<key>LimitLoadToSessionType<\/key>\s*<string>Aqua<\/string>/);
  assert.match(u.files[0].content, /<key>ProcessType<\/key>\s*<string>Interactive<\/string>/);
});

test("unit PATH covers homebrew, /usr/local and ~/.arkaos/bin (nvm installs degrade to the app's logged which-guard)", () => {
  const u = unitFor("darwin", ctx);
  const path = u.files[0].content.match(/<key>PATH<\/key>\s*<string>([^<]*)<\/string>/)[1];
  assert.ok(path.includes("/opt/homebrew/bin"), path);
  assert.ok(path.includes("/usr/local/bin"), path);
  assert.ok(path.includes("/Users/x/.arkaos/bin"), path);
});

test("plist values are XML-escaped — '&' and '<' are legal in macOS paths (QG M1)", () => {
  assert.equal(xmlEscape('a&b<c>"d\'e'), "a&amp;b&lt;c&gt;&quot;d&apos;e");
  const u = unitFor("darwin", {
    home: "/Users/A & B",
    pythonPath: "/Users/A & B/.arkaos/venv/bin/python",
    scriptPath: "/Users/A & B/.arkaos/bin/arka-menubar.py",
  });
  assert.ok(u.files[0].content.includes("/Users/A &amp; B/.arkaos/venv/bin/python"));
  assert.ok(!/<string>[^<]*& [^<]*<\/string>/.test(u.files[0].content),
    "raw ampersand leaked into plist");
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

// Safety-critical default-on promise: a persisted opt-out must NEVER be
// re-enabled by install/update flows. The repoRoot is deliberately empty
// so even a regression cannot reach launchctl (enable() bails before any
// exec when the source script is missing) — the assertions still catch it
// because a regression would return "partial", not "optout".
test("ensureDefaultEnabled honors the opt-out marker and does not re-enable", { skip: process.platform !== "darwin" }, () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "arka-menubar-optout-repo-"));
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-optout-home-"));
  try {
    mkdirSync(join(home, ".arkaos"), { recursive: true });
    writeFileSync(optoutPath(home), "2026-07-23T00:00:00Z", "utf8");
    const r = ensureDefaultEnabled({ repoRoot, home });
    assert.deepEqual(r, { action: "optout" });
    assert.ok(existsSync(optoutPath(home)), "opt-out marker must survive");
    assert.ok(!existsSync(menubarScriptPath(home)), "script must not be deployed");
    const plist = join(home, "Library", "LaunchAgents", `${MENUBAR_LABEL}.plist`);
    assert.ok(!existsSync(plist), "plist must not be written");
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

test("menu: core actions always present (incl. discoverable disable), quit last", { skip: !HAVE_PY }, () => {
  const items = pyProbe("--print-menu", { ollama: "absent" });
  for (const id of ["check_updates", "open_dashboard", "doctor", "autoupdate_toggle", "disable"]) {
    assert.ok(items.includes(id), `missing ${id}`);
  }
  assert.equal(items[items.length - 1], "quit");
  assert.equal(items[items.length - 2], "disable",
    "permanent opt-out must be discoverable next to Quit (QG M7)");
});

// The live ollama probe is gated on the local-ai profile — the only one
// that ever surfaces Start Ollama. A fake `ollama` on PATH writes a marker
// when spawned: essential must never touch it, local-ai must.
test("menu: ollama probe spawns ONLY on the local-ai profile", { skip: !HAVE_PY || process.platform === "win32" }, () => {
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-probe-"));
  try {
    const arka = join(home, ".arkaos");
    const fakeBin = join(home, "fakebin");
    const marker = join(home, "probe-spawned");
    mkdirSync(arka, { recursive: true });
    mkdirSync(fakeBin, { recursive: true });
    writeFileSync(join(fakeBin, "ollama"), `#!/bin/sh\ntouch "${marker}"\n`);
    chmodSync(join(fakeBin, "ollama"), 0o755);
    const probe = () => {
      const run = spawnSync("python3", [MENUBAR_PY, "--print-menu"], {
        env: {
          ...process.env,
          ARKA_MENUBAR_HOME: home,
          ARKA_MENUBAR_OLLAMA: "", // force the real (fake-PATH) probe path
          PATH: `${fakeBin}:${process.env.PATH}`,
        },
        encoding: "utf8",
        timeout: 15000,
      });
      assert.equal(run.status, 0, `stderr: ${run.stderr}`);
      return JSON.parse(run.stdout);
    };

    writeFileSync(join(arka, "profile.json"), JSON.stringify({ installProfile: "essential" }));
    probe();
    assert.ok(!existsSync(marker), "essential profile must not spawn ollama");

    writeFileSync(join(arka, "profile.json"), JSON.stringify({ installProfile: "local-ai" }));
    probe();
    assert.ok(existsSync(marker), "local-ai profile must run the live probe");
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

// ── Part 3: doctor probe, distribution + contract locks (QG round 1) ───

test("menubarHealthy: every branch, launchd never touched (QG M2)", () => {
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-health-"));
  try {
    // Not applicable off macOS.
    assert.equal(menubarHealthy({ home, platform: "linux" }), true);
    // Not installed → unhealthy (exec must not even be consulted).
    assert.equal(
      menubarHealthy({ home, platform: "darwin", exec: () => { throw new Error("never"); } }),
      false,
    );
    // Persisted opt-out is a healthy, chosen state.
    mkdirSync(join(home, ".arkaos"), { recursive: true });
    writeFileSync(optoutPath(home), "x");
    assert.equal(
      menubarHealthy({ home, platform: "darwin", exec: () => { throw new Error("never"); } }),
      true,
    );
    rmSync(optoutPath(home));
    // Installed: healthy iff `launchctl list <label>` reports the job.
    mkdirSync(join(home, "Library", "LaunchAgents"), { recursive: true });
    writeFileSync(join(home, "Library", "LaunchAgents", `${MENUBAR_LABEL}.plist`), "<plist/>");
    mkdirSync(dirname(menubarScriptPath(home)), { recursive: true });
    writeFileSync(menubarScriptPath(home), "#!/usr/bin/env python3\n");
    const calls = [];
    const exec = (file, args) => { calls.push([file, ...args]); return true; };
    assert.equal(menubarHealthy({ home, platform: "darwin", exec }), true);
    assert.deepEqual(calls, [["launchctl", "list", MENUBAR_LABEL]]);
    assert.equal(
      menubarHealthy({ home, platform: "darwin", exec: () => false }),
      false,
      "files present but job not loaded must be unhealthy",
    );
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("package.json ships bin/arka-menubar.py — the file-by-file bin/ allowlist (QG M6)", () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
  assert.ok(pkg.files.includes("bin/arka-menubar.py"),
    "missing from files: the tarball silently drops the menu bar app");
});

test("opt-out marker names are locked against the REAL modules, not themselves (QG M8)", () => {
  const pySource = readFileSync(MENUBAR_PY, "utf8");
  // Python reads the autoupdate marker the PR-1 daemon actually writes…
  assert.ok(autoupdateOptoutPath("/x").endsWith("autoupdate.optout"));
  assert.match(pySource, /AUTOUPDATE_OPTOUT_BASENAME = "autoupdate\.optout"/);
  // …and the menubar marker installer/menubar.js actually honors.
  assert.ok(optoutPath("/x").endsWith("menubar.optout"));
  assert.match(pySource, /MENUBAR_OPTOUT_BASENAME = "menubar\.optout"/);
});

// The plist's last-resort interpreter is the macOS system python (3.9).
// PEP 604 annotations without the __future__ import crash at def time
// there — before the guarded rumps import ever runs (QG B1).
const SYSTEM_PY = "/usr/bin/python3";
const HAVE_SYSTEM_PY = existsSync(SYSTEM_PY);

test("script runs under the fallback /usr/bin/python3 (QG B1)", { skip: !HAVE_SYSTEM_PY }, () => {
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-syspy-"));
  try {
    const run = spawnSync(SYSTEM_PY, [MENUBAR_PY, "--print-state"], {
      env: { ...process.env, ARKA_MENUBAR_HOME: home },
      encoding: "utf8",
      timeout: 15000,
    });
    assert.equal(run.status, 0, `stderr: ${run.stderr}`);
    assert.equal(JSON.parse(run.stdout).profile, "essential");
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("app run is a clean exit 0 when rumps is broken AND when opted out (never a crashing login item)", { skip: !HAVE_PY }, () => {
  const home = mkdtempSync(join(tmpdir(), "arka-menubar-guard-"));
  try {
    // A rumps shim that raises at import SHADOWS any real rumps, so the
    // app can never actually launch — this exercises the guard for real.
    const shimDir = join(home, "shim");
    mkdirSync(shimDir, { recursive: true });
    writeFileSync(join(shimDir, "rumps.py"), "raise ImportError('broken by test')\n");
    const runApp = () =>
      spawnSync("python3", [MENUBAR_PY], {
        env: { ...process.env, ARKA_MENUBAR_HOME: home, PYTHONPATH: shimDir },
        encoding: "utf8",
        timeout: 15000,
      });

    const broken = runApp();
    assert.equal(broken.status, 0, `stderr: ${broken.stderr}`);

    // Startup opt-out guard (QG M7): marker makes RunAtLoad a no-op.
    mkdirSync(join(home, ".arkaos"), { recursive: true });
    writeFileSync(join(home, ".arkaos", "menubar.optout"), "x");
    const optedOut = runApp();
    assert.equal(optedOut.status, 0, `stderr: ${optedOut.stderr}`);
    if (process.platform === "darwin") {
      assert.match(optedOut.stdout, /opt-out/);
    }
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("--help exits 0 with usage; unknown flags exit 2, never launch the app", { skip: !HAVE_PY }, () => {
  const helpRun = spawnSync("python3", [MENUBAR_PY, "--help"], {
    encoding: "utf8", timeout: 15000,
  });
  assert.equal(helpRun.status, 0);
  assert.match(helpRun.stdout, /--print-state/);
  const badRun = spawnSync("python3", [MENUBAR_PY, "--bogus"], {
    encoding: "utf8", timeout: 15000,
  });
  assert.equal(badRun.status, 2);
  assert.match(badRun.stdout, /unknown option/);
});
