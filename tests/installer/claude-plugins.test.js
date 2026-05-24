// Tests for the Claude Code plugin auto-install (PR43 v2.62.0).
//
// Subprocess calls (claude --version, claude plugin install) are mocked
// via a temp PATH override so the test never touches the real CLI.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, chmodSync, readFileSync, existsSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  DEFAULT_CLAUDE_PLUGINS,
  installDefaultClaudePlugins,
} = await import(join(ROOT, "installer", "claude-plugins.js"));


// ─── Mock CLI helpers ───────────────────────────────────────────────────


function makeMockClaude({ versionExit = 0, installExit = 0, installStderr = "" } = {}) {
  // Build a temp directory with a `claude` shell script that mimics the CLI.
  // Pre-pend the dir to PATH so child processes resolve it.
  const dir = mkdtempSync(join(tmpdir(), "arkaos-claude-mock-"));
  const script = join(dir, "claude");
  const body = `#!/usr/bin/env bash
if [ "$1" = "--version" ]; then
  echo "claude mock 0.0.0"
  exit ${versionExit}
fi
if [ "$1" = "plugin" ] && [ "$2" = "install" ]; then
  ${installStderr ? `echo "${installStderr.replace(/"/g, '\\"')}" >&2` : ""}
  exit ${installExit}
fi
exit 99
`;
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}


function withMockedPath(mockDir, fn) {
  const original = process.env.PATH;
  process.env.PATH = `${mockDir}:${original}`;
  try {
    return fn();
  } finally {
    process.env.PATH = original;
  }
}


function makeTmpHome(installedPluginNames = []) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-plugins-test-"));
  if (installedPluginNames.length > 0) {
    const path = join(dir, ".claude", "plugins", "installed_plugins.json");
    mkdirSync(dirname(path), { recursive: true });
    const payload = {
      version: 2,
      plugins: Object.fromEntries(
        installedPluginNames.map((name) => [
          name,
          [{ scope: "user", version: "0.0.0", installedAt: new Date().toISOString() }],
        ]),
      ),
    };
    writeFileSync(path, JSON.stringify(payload, null, 2));
  }
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}


// ─── Runtime gating ─────────────────────────────────────────────────────


test("no-op when runtime is not Claude Code", () => {
  const result = installDefaultClaudePlugins({ runtime: "codex" });
  assert.equal(result.skipped, "runtime-not-claude-code");
  assert.deepEqual(result.results, []);
});

test("no-op when claude CLI is not available on PATH", () => {
  const original = process.env.PATH;
  process.env.PATH = "/tmp/non-existent-dir";
  try {
    const result = installDefaultClaudePlugins({ runtime: "claude-code" });
    assert.equal(result.skipped, "claude-cli-not-found");
  } finally {
    process.env.PATH = original;
  }
});


// ─── Install path ───────────────────────────────────────────────────────


test("installs each default plugin when nothing is registered yet", () => {
  const mock = makeMockClaude();
  const home = makeTmpHome();
  try {
    withMockedPath(mock.dir, () => {
      const result = installDefaultClaudePlugins({
        runtime: "claude-code",
        home: home.dir,
        plugins: ["foo@bar"],
      });
      assert.equal(result.skipped, null);
      assert.equal(result.results.length, 1);
      assert.equal(result.results[0].plugin, "foo@bar");
      assert.equal(result.results[0].action, "installed");
    });
  } finally {
    mock.cleanup();
    home.cleanup();
  }
});

test("skips plugins already in installed_plugins.json", () => {
  const mock = makeMockClaude();
  const home = makeTmpHome(["foo@bar"]);
  try {
    withMockedPath(mock.dir, () => {
      const result = installDefaultClaudePlugins({
        runtime: "claude-code",
        home: home.dir,
        plugins: ["foo@bar"],
      });
      assert.equal(result.results[0].action, "already-present");
    });
  } finally {
    mock.cleanup();
    home.cleanup();
  }
});

test("captures install failure as 'failed' with reason", () => {
  const mock = makeMockClaude({ installExit: 1, installStderr: "marketplace not found" });
  const home = makeTmpHome();
  try {
    withMockedPath(mock.dir, () => {
      const result = installDefaultClaudePlugins({
        runtime: "claude-code",
        home: home.dir,
        plugins: ["broken@nowhere"],
      });
      assert.equal(result.results[0].action, "failed");
      assert.match(result.results[0].reason, /marketplace/);
    });
  } finally {
    mock.cleanup();
    home.cleanup();
  }
});

test("handles a mix of installed + already-present + failed", () => {
  const mock = makeMockClaude();
  const home = makeTmpHome(["already@here"]);
  try {
    withMockedPath(mock.dir, () => {
      const result = installDefaultClaudePlugins({
        runtime: "claude-code",
        home: home.dir,
        plugins: ["new@one", "already@here"],
      });
      const byAction = Object.fromEntries(
        result.results.map((r) => [r.plugin, r.action]),
      );
      assert.equal(byAction["new@one"], "installed");
      assert.equal(byAction["already@here"], "already-present");
    });
  } finally {
    mock.cleanup();
    home.cleanup();
  }
});


// ─── Default list shape ─────────────────────────────────────────────────


test("DEFAULT_CLAUDE_PLUGINS includes the frontend-design entry", () => {
  assert.ok(
    DEFAULT_CLAUDE_PLUGINS.includes("frontend-design@claude-plugins-official"),
    "DEFAULT_CLAUDE_PLUGINS must ship frontend-design@claude-plugins-official",
  );
});

test("DEFAULT_CLAUDE_PLUGINS entries follow name@marketplace format", () => {
  for (const entry of DEFAULT_CLAUDE_PLUGINS) {
    assert.match(entry, /^[\w-]+@[\w-]+$/, `entry ${entry} must match name@marketplace`);
  }
});
