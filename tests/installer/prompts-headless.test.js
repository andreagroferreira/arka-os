// Foundation PR-3 — the headless contract of the setup wizard.
//
// Rule (.claude/rules/node-installer.md): NO interactive prompts during
// headless/CI runs. An upgrade with a valid profile.json must
// short-circuit before ever touching stdin, and the returned config must
// now carry `installProfile` (defaulted to "essential" for profiles
// written before PR-3).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";

import { loadExistingProfileConfig } from "../../installer/prompts.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PROMPTS_URL = pathToFileURL(join(ROOT, "installer", "prompts.js")).href;

function withTempInstallDir(profileBody, fn) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-prompts-test-"));
  try {
    if (profileBody !== null) {
      writeFileSync(join(dir, "profile.json"), profileBody);
    }
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// ── loadExistingProfileConfig — installProfile carry/default ──────────────

test("valid profile without installProfile defaults to essential", () => {
  withTempInstallDir(
    JSON.stringify({ language: "en", role: "developer" }),
    (dir) => {
      const config = loadExistingProfileConfig(dir);
      assert.ok(config, "valid profile must short-circuit");
      assert.equal(config.installProfile, "essential");
      assert.equal(config.installDir, dir);
      // Upgrade semantics unchanged: no feature re-opt-in, knowledge on.
      assert.equal(config.installDashboard, false);
      assert.equal(config.installKnowledge, true);
      assert.equal(config.installTranscription, false);
    },
  );
});

test("installProfile is carried from profile.json when valid", () => {
  withTempInstallDir(
    JSON.stringify({ language: "pt", role: "founder", installProfile: "complete" }),
    (dir) => {
      const config = loadExistingProfileConfig(dir);
      assert.equal(config.installProfile, "complete");
    },
  );
});

test("invalid installProfile in profile.json degrades to essential", () => {
  withTempInstallDir(
    JSON.stringify({ language: "pt", role: "founder", installProfile: "yolo" }),
    (dir) => {
      const config = loadExistingProfileConfig(dir);
      assert.equal(config.installProfile, "essential");
    },
  );
});

test("missing required fields still force the wizard (null)", () => {
  withTempInstallDir(JSON.stringify({ language: "en" }), (dir) => {
    assert.equal(loadExistingProfileConfig(dir), null);
  });
});

test("corrupt profile.json still forces the wizard (null)", () => {
  withTempInstallDir("{broken", (dir) => {
    assert.equal(loadExistingProfileConfig(dir), null);
  });
});

test("missing profile.json still forces the wizard (null)", () => {
  withTempInstallDir(null, (dir) => {
    assert.equal(loadExistingProfileConfig(dir), null);
  });
});

// ── runSetupPrompts(true) — headless subprocess, stdin closed ─────────────
// The real regression this locks: an upgrade run from a pipe (CI, the
// auto-update daemon, `--force </dev/null`) must exit 0 without ever
// prompting. A hang here means a prompt reached stdin — spawnSync's
// timeout converts that hang into a visible failure.

function runHeadlessUpgrade(profileBody) {
  const home = mkdtempSync(join(tmpdir(), "arkaos-home-test-"));
  try {
    mkdirSync(join(home, ".arkaos"), { recursive: true });
    writeFileSync(join(home, ".arkaos", "profile.json"), profileBody);
    const code = [
      `const m = await import(${JSON.stringify(PROMPTS_URL)});`,
      `const c = await m.runSetupPrompts(true);`,
      `console.log("RESULT:" + JSON.stringify({ installProfile: c.installProfile, language: c.language }));`,
    ].join("\n");
    return spawnSync(process.execPath, ["--input-type=module", "-e", code], {
      // HOME (POSIX) + USERPROFILE (Windows) point homedir() at the temp home.
      env: { ...process.env, HOME: home, USERPROFILE: home },
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 15000,
      encoding: "utf-8",
    });
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
}

test("headless upgrade short-circuits without prompting (exit 0, no hang)", () => {
  const run = runHeadlessUpgrade(
    JSON.stringify({ language: "en", role: "developer" }),
  );
  assert.equal(run.signal, null, `killed by ${run.signal} — wizard prompted on a closed stdin`);
  assert.equal(run.status, 0, `stderr: ${run.stderr}`);
  assert.match(run.stdout, /using existing profile/);
  const payload = JSON.parse(run.stdout.match(/RESULT:(\{.*\})/)[1]);
  assert.equal(payload.installProfile, "essential",
    "pre-PR-3 profiles without installProfile must default to essential");
  assert.equal(payload.language, "en");
});

test("headless upgrade carries a persisted installProfile through", () => {
  const run = runHeadlessUpgrade(
    JSON.stringify({ language: "pt", role: "founder", installProfile: "local-ai" }),
  );
  assert.equal(run.status, 0, `stderr: ${run.stderr}`);
  const payload = JSON.parse(run.stdout.match(/RESULT:(\{.*\})/)[1]);
  assert.equal(payload.installProfile, "local-ai");
});
