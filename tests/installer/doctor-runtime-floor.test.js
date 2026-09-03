// Runtime Sync PR1 — the Claude Code version floor the doctor enforces.
//
// The floor is a pure comparison over `claude --version` text; the wired
// check is exercised through a PATH-prepended mock `claude` so the real
// CLI is never consulted (same pattern as claude-plugins.test.js).

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, chmodSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  checks,
  CLAUDE_CODE_MIN_VERSION,
  CLAUDE_CODE_MIN_VERSION_REASON,
  parseClaudeCodeVersion,
  versionAtLeast,
} from "../../installer/doctor.js";
import { IS_WINDOWS } from "../../installer/platform.js";

const byName = Object.fromEntries(checks.map((c) => [c.name, c]));
const entry = byName["claude-code-version"];

test("the floor is 2.1.257 and the check names the reason", () => {
  assert.equal(CLAUDE_CODE_MIN_VERSION, "2.1.257");
  assert.ok(entry, "missing doctor check: claude-code-version");
  assert.equal(entry.severity, "warn", "advisory: another runtime may be in use");
  assert.ok(entry.description.includes("2.1.257+"), entry.description);
  assert.ok(entry.description.includes(CLAUDE_CODE_MIN_VERSION_REASON));
  for (const reason of [
    "Fable 5.1",
    "CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
    "permissions.blockReadsOutsideWorkingDirectories",
  ]) {
    assert.ok(CLAUDE_CODE_MIN_VERSION_REASON.includes(reason), reason);
  }
});

test("parseClaudeCodeVersion tolerates the CLI's decorations", () => {
  assert.deepEqual(parseClaudeCodeVersion("2.1.259 (Claude Code)"), [2, 1, 259]);
  assert.deepEqual(parseClaudeCodeVersion("claude mock 0.0.0"), [0, 0, 0]);
  assert.equal(parseClaudeCodeVersion("no version here"), null);
  assert.equal(parseClaudeCodeVersion(""), null);
  assert.equal(parseClaudeCodeVersion(null), null);
  assert.equal(parseClaudeCodeVersion(undefined), null);
});

test("versionAtLeast compares numerically, component by component", () => {
  assert.equal(versionAtLeast("2.1.240 (Claude Code)", "2.1.257"), false);
  assert.equal(versionAtLeast("2.1.256", "2.1.257"), false);
  assert.equal(versionAtLeast("2.1.257", "2.1.257"), true);
  assert.equal(versionAtLeast("2.1.259 (Claude Code)", "2.1.257"), true);
  assert.equal(versionAtLeast("2.2.0", "2.1.257"), true);
  assert.equal(versionAtLeast("3.0.0", "2.1.257"), true);
  assert.equal(versionAtLeast("1.9.999", "2.1.257"), false);
  // numeric, not lexical: "1000" > "257" even though "1" < "2"
  assert.equal(versionAtLeast("2.1.1000", "2.1.257"), true);
  assert.equal(versionAtLeast("claude mock 0.0.0", "2.1.257"), false);
  assert.equal(versionAtLeast("garbage", "2.1.257"), false);
  assert.equal(versionAtLeast(null, "2.1.257"), false);
  assert.equal(versionAtLeast("2.1.259", "not-a-floor"), false);
});

// ─── wired check, through a PATH-prepended mock `claude` ────────────────

function withMockClaude({ version, exit = 0, present = true }, fn) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-claude-floor-"));
  if (present) {
    const script = join(dir, "claude");
    writeFileSync(
      script,
      `#!/usr/bin/env bash\nif [ "$1" = "--version" ]; then\n  echo "${version}"\n  exit ${exit}\nfi\nexit 99\n`
    );
    chmodSync(script, 0o755);
  }
  const savedPath = process.env.PATH;
  // The mock dir first; then only the system dirs, so `which` resolves
  // but a globally installed `claude` (this machine has one) does not.
  process.env.PATH = `${dir}:/usr/bin:/bin`;
  try {
    return fn();
  } finally {
    process.env.PATH = savedPath;
    rmSync(dir, { recursive: true, force: true });
  }
}

test("an older binary warns and the fix names the detected build", { skip: IS_WINDOWS }, () => {
  withMockClaude({ version: "2.1.240 (Claude Code)" }, () => {
    assert.equal(entry.check(), false);
    const fix = entry.fix();
    assert.ok(fix.includes("Detected 2.1.240"), fix);
    assert.ok(fix.includes("2.1.257+"), fix);
    assert.ok(fix.includes(CLAUDE_CODE_MIN_VERSION_REASON), fix);
    assert.ok(fix.includes("npm install -g @anthropic-ai/claude-code@latest"), fix);
  });
});

test("a binary at or above the floor passes", { skip: IS_WINDOWS }, () => {
  withMockClaude({ version: "2.1.257 (Claude Code)" }, () => {
    assert.equal(entry.check(), true);
  });
  withMockClaude({ version: "2.1.259 (Claude Code)" }, () => {
    assert.equal(entry.check(), true);
  });
});

test("a binary that cannot answer --version warns with a parse hint", { skip: IS_WINDOWS }, () => {
  withMockClaude({ version: "2.1.259", exit: 1 }, () => {
    assert.equal(entry.check(), false, "non-zero exit is not a pass");
    assert.ok(entry.fix().includes("no parsable"), entry.fix());
  });
  withMockClaude({ version: "claude mock 0.0.0" }, () => {
    assert.equal(entry.check(), false);
    assert.ok(entry.fix().includes("Detected 0.0.0"), entry.fix());
  });
});

test("no claude binary at all is not applicable, not a warning", { skip: IS_WINDOWS }, () => {
  withMockClaude({ present: false }, () => {
    assert.equal(entry.check(), true);
  });
});
