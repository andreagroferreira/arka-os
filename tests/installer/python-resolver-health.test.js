/**
 * Tests for ensureVenvHealthy() + diagnoseVenv() in python-resolver.js.
 *
 * PR2 of the Squad Intelligence Upgrade — the dashboard hotfix that closes
 * the long-standing "venv was created but is broken" failure mode where:
 *  - ~/.arkaos/venv/bin/python is a symlink to a Homebrew-rotated python
 *    that no longer exists on disk, so ensureVenv() incorrectly reports
 *    "venv exists" because existsSync follows the symlink and the target
 *    is gone (returns false) OR Node resolves the symlink to a stale path.
 *  - start-dashboard.sh falls back to ambient `python3`, which usually
 *    doesn't have sqlite-vec / fastembed installed, so the dashboard
 *    starts in a half-broken state and the operator hits Vector-Search
 *    failures with no obvious culprit.
 *
 * The tests use real Python from the system to create / corrupt tmp venvs
 * — they are integration-style, not pure unit tests. Each test isolates
 * its venv under tmpdir so no global state is mutated.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, symlinkSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execSync } from "node:child_process";

import {
  diagnoseVenv,
  ensureVenvHealthy,
} from "../../installer/python-resolver.js";


function makeTmp() {
  return mkdtempSync(join(tmpdir(), "arka-venv-test-"));
}


function cleanup(dir) {
  try { rmSync(dir, { recursive: true, force: true }); } catch {}
}


function createRealVenv(parent) {
  const venvDir = join(parent, "venv");
  // Use the same Python that runs Node's child_process — guaranteed present.
  execSync(`python3 -m venv "${venvDir}"`, { stdio: "pipe", timeout: 30000 });
  return venvDir;
}


// ─── diagnoseVenv() ─────────────────────────────────────────────────────


test("diagnoseVenv: missing venv directory → reason=missing", () => {
  const tmp = makeTmp();
  try {
    const result = diagnoseVenv(join(tmp, "no-such-venv"));
    assert.equal(result.healthy, false);
    assert.equal(result.reason, "missing");
  } finally {
    cleanup(tmp);
  }
});


test("diagnoseVenv: directory exists but no bin/python → reason=missing", () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    // Make the dir but no Python binary
    execSync(`mkdir -p "${venvDir}/bin"`);
    const result = diagnoseVenv(venvDir);
    assert.equal(result.healthy, false);
    assert.equal(result.reason, "missing");
  } finally {
    cleanup(tmp);
  }
});


test("diagnoseVenv: broken symlink to nonexistent target → reason=broken-symlink", () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    execSync(`mkdir -p "${venvDir}/bin"`);
    // Point bin/python at a path that doesn't exist (simulates Homebrew rotation)
    symlinkSync("/nonexistent/python3.99", join(venvDir, "bin", "python"));
    const result = diagnoseVenv(venvDir);
    assert.equal(result.healthy, false);
    assert.equal(result.reason, "broken-symlink");
  } finally {
    cleanup(tmp);
  }
});


test("diagnoseVenv: healthy venv with system python → reason=ok", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  try {
    const venvDir = createRealVenv(tmp);
    const result = diagnoseVenv(venvDir);
    assert.equal(result.healthy, true);
    assert.equal(result.reason, "ok");
    assert.ok(result.pythonPath);
    assert.ok(existsSync(result.pythonPath));
  } finally {
    cleanup(tmp);
  }
});


test("diagnoseVenv: python version probe fails → reason=version-failed", () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    execSync(`mkdir -p "${venvDir}/bin"`);
    // Non-executable file at bin/python — exists but cannot run
    writeFileSync(join(venvDir, "bin", "python"), "not a real binary");
    const result = diagnoseVenv(venvDir);
    assert.equal(result.healthy, false);
    assert.ok(["version-failed", "broken-symlink"].includes(result.reason));
  } finally {
    cleanup(tmp);
  }
});


// ─── ensureVenvHealthy() ────────────────────────────────────────────────


test("ensureVenvHealthy: missing → creates fresh venv → repaired=true", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    const result = ensureVenvHealthy({ venvDir, skipDeps: true });
    assert.equal(result.healthy, true);
    assert.equal(result.repaired, true);
    assert.ok(existsSync(join(venvDir, "bin", "python")));
  } finally {
    cleanup(tmp);
  }
});


test("ensureVenvHealthy: broken-symlink → --clear recreate → repaired=true", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    execSync(`mkdir -p "${venvDir}/bin"`);
    symlinkSync("/nonexistent/python3.99", join(venvDir, "bin", "python"));
    const result = ensureVenvHealthy({ venvDir, skipDeps: true });
    assert.equal(result.healthy, true);
    assert.equal(result.repaired, true);
    // After repair, bin/python should be a real working symlink
    const pythonPath = join(venvDir, "bin", "python");
    assert.ok(existsSync(pythonPath));
    const version = execSync(`"${pythonPath}" --version 2>&1`).toString();
    assert.ok(version.includes("Python 3"));
  } finally {
    cleanup(tmp);
  }
});


test("ensureVenvHealthy: healthy venv → no-op → repaired=false", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  try {
    const venvDir = createRealVenv(tmp);
    const result = ensureVenvHealthy({ venvDir, skipDeps: true });
    assert.equal(result.healthy, true);
    assert.equal(result.repaired, false);
  } finally {
    cleanup(tmp);
  }
});


test("ensureVenvHealthy: reason is informative on success", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  try {
    const venvDir = join(tmp, "venv");
    const result = ensureVenvHealthy({ venvDir, skipDeps: true });
    assert.ok(typeof result.reason === "string");
    assert.ok(result.reason.length > 0);
  } finally {
    cleanup(tmp);
  }
});


test("ensureVenvHealthy: log callback invoked with progress messages", { skip: process.platform === "win32" }, () => {
  const tmp = makeTmp();
  const logs = [];
  try {
    const venvDir = join(tmp, "venv");
    ensureVenvHealthy({
      venvDir,
      skipDeps: true,
      log: (msg) => logs.push(msg),
    });
    assert.ok(logs.length > 0, "expected at least one log line");
    // Should mention "venv" somewhere in the logs
    assert.ok(
      logs.some((line) => /venv/i.test(line)),
      `expected logs to mention venv, got: ${logs.join(" | ")}`
    );
  } finally {
    cleanup(tmp);
  }
});
