// Tests for the frontend UI/UX tooling setup (Magic MCP + Motion AI Kit).
//
// Subprocess calls (claude --version, claude mcp list/add, npx motion-ai)
// are mocked via a temp PATH override so the test never touches the real
// CLIs. The interactive key prompt is never exercised because the test
// runner has no TTY (process.stdin.isTTY is falsy) — promptMagicKey
// short-circuits to "" exactly as it does in headless/CI installs.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, chmodSync, readFileSync, rmSync, existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  ensureMagicApiKey,
  registerMagicMcp,
  installMotionKit,
  setupFrontendTooling,
} = await import(join(ROOT, "installer", "frontend-tooling.js"));


// ─── Mock CLI helpers ───────────────────────────────────────────────────


function makeMockClaude({
  versionExit = 0,
  mcpListStdout = "",
  mcpAddExit = 0,
  mcpAddStderr = "",
} = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-ft-claude-mock-"));
  const script = join(dir, "claude");
  const body = `#!/usr/bin/env bash
if [ "$1" = "--version" ]; then
  echo "claude mock 0.0.0"
  exit ${versionExit}
fi
if [ "$1" = "mcp" ] && [ "$2" = "list" ]; then
  echo "${mcpListStdout.replace(/"/g, '\\"')}"
  exit 0
fi
if [ "$1" = "mcp" ] && [ "$2" = "add" ]; then
  ${mcpAddStderr ? `echo "${mcpAddStderr.replace(/"/g, '\\"')}" >&2` : ""}
  exit ${mcpAddExit}
fi
exit 99
`;
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

function makeMockNpx({ exit = 0, stderr = "" } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-ft-npx-mock-"));
  const script = join(dir, "npx");
  const body = `#!/usr/bin/env bash
${stderr ? `echo "${stderr.replace(/"/g, '\\"')}" >&2` : ""}
exit ${exit}
`;
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

// Keeps the PATH override in place for the FULL duration of the callback,
// async or sync. Restoring synchronously for an async fn would let its
// spawnSync calls resolve the REAL binaries after PATH was reset — which
// would mutate the operator's actual Claude config. So: sync fn restores
// immediately (assertions already ran); async fn restores via .finally
// once the returned promise settles. Callers can await the result.
function withMockedPath(mockDirs, fn) {
  const original = process.env.PATH;
  process.env.PATH = `${mockDirs.join(":")}:${original}`;
  let result;
  try {
    result = fn();
  } catch (err) {
    process.env.PATH = original;
    throw err;
  }
  if (result && typeof result.then === "function") {
    return result.finally(() => { process.env.PATH = original; });
  }
  process.env.PATH = original;
  return result;
}

function makeTmpHome(keys = null) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-ft-home-"));
  // ~/.arkaos always exists by the time tooling runs in a real install;
  // mirror that so marker writes (motion kit) behave as in production.
  mkdirSync(join(dir, ".arkaos"), { recursive: true });
  if (keys) {
    writeFileSync(join(dir, ".arkaos", "keys.json"), JSON.stringify(keys, null, 2));
  }
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}


// ─── ensureMagicApiKey ──────────────────────────────────────────────────


test("ensureMagicApiKey returns the stored key without prompting", async () => {
  const home = makeTmpHome({ MAGIC_API_KEY: "stored-key-123" });
  try {
    const key = await ensureMagicApiKey({ home: home.dir });
    assert.equal(key, "stored-key-123");
  } finally {
    home.cleanup();
  }
});

test("ensureMagicApiKey returns '' in headless context when key is missing", async () => {
  const home = makeTmpHome();
  try {
    // No TTY in the test runner → promptMagicKey short-circuits to "".
    const key = await ensureMagicApiKey({ home: home.dir });
    assert.equal(key, "");
  } finally {
    home.cleanup();
  }
});


// ─── registerMagicMcp ───────────────────────────────────────────────────


test("registerMagicMcp skips on a non-Claude runtime", () => {
  const result = registerMagicMcp({ runtime: "codex", apiKey: "k" });
  assert.equal(result.action, "skipped");
  assert.equal(result.reason, "runtime-not-claude-code");
});

test("registerMagicMcp skips when no API key is available", () => {
  const mock = makeMockClaude();
  try {
    withMockedPath([mock.dir], () => {
      const result = registerMagicMcp({ runtime: "claude-code", apiKey: "" });
      assert.equal(result.action, "skipped");
      assert.equal(result.reason, "no-api-key");
    });
  } finally {
    mock.cleanup();
  }
});

test("registerMagicMcp registers when CLI present, key set, and not yet registered", () => {
  const mock = makeMockClaude({ mcpListStdout: "obsidian\ncontext7" });
  try {
    withMockedPath([mock.dir], () => {
      const result = registerMagicMcp({ runtime: "claude-code", apiKey: "k" });
      assert.equal(result.action, "registered");
    });
  } finally {
    mock.cleanup();
  }
});

test("registerMagicMcp reports already-present when magic is in mcp list", () => {
  const mock = makeMockClaude({ mcpListStdout: "magic: npx -y @21st-dev/magic" });
  try {
    withMockedPath([mock.dir], () => {
      const result = registerMagicMcp({ runtime: "claude-code", apiKey: "k" });
      assert.equal(result.action, "already-present");
    });
  } finally {
    mock.cleanup();
  }
});

test("registerMagicMcp captures failure as 'failed' with reason", () => {
  const mock = makeMockClaude({ mcpListStdout: "obsidian", mcpAddExit: 1, mcpAddStderr: "scope error" });
  try {
    withMockedPath([mock.dir], () => {
      const result = registerMagicMcp({ runtime: "claude-code", apiKey: "k" });
      assert.equal(result.action, "failed");
      assert.match(result.reason, /scope/);
    });
  } finally {
    mock.cleanup();
  }
});


// ─── installMotionKit ───────────────────────────────────────────────────


test("installMotionKit skips on a non-Claude runtime", () => {
  const result = installMotionKit({ runtime: "cursor" });
  assert.equal(result.action, "skipped");
  assert.equal(result.reason, "runtime-not-claude-code");
});

test("installMotionKit skips when the claude CLI is unavailable", () => {
  const npx = makeMockNpx({ exit: 0 });
  const home = makeTmpHome();
  try {
    // Only npx is on PATH — no `claude` binary mock.
    const original = process.env.PATH;
    process.env.PATH = `${npx.dir}:/tmp/non-existent-dir`;
    try {
      const result = installMotionKit({ runtime: "claude-code", home: home.dir });
      assert.equal(result.action, "skipped");
      assert.equal(result.reason, "claude-cli-not-found");
    } finally {
      process.env.PATH = original;
    }
  } finally {
    npx.cleanup();
    home.cleanup();
  }
});

test("installMotionKit installs on success and writes the idempotency marker", () => {
  const claude = makeMockClaude();
  const npx = makeMockNpx({ exit: 0 });
  const home = makeTmpHome();
  try {
    withMockedPath([claude.dir, npx.dir], () => {
      const result = installMotionKit({ runtime: "claude-code", home: home.dir });
      assert.equal(result.action, "installed");
    });
    // Marker now exists.
    assert.ok(existsSync(join(home.dir, ".arkaos", ".motion-kit-installed")));
  } finally {
    claude.cleanup();
    npx.cleanup();
    home.cleanup();
  }
});

test("installMotionKit is idempotent — skips when the marker already exists", () => {
  const claude = makeMockClaude();
  const npx = makeMockNpx({ exit: 0 });
  const home = makeTmpHome();
  try {
    // Pre-seed the marker.
    mkdirSync(join(home.dir, ".arkaos"), { recursive: true });
    writeFileSync(join(home.dir, ".arkaos", ".motion-kit-installed"), "2026-05-30");
    withMockedPath([claude.dir, npx.dir], () => {
      const result = installMotionKit({ runtime: "claude-code", home: home.dir });
      assert.equal(result.action, "already-present");
    });
  } finally {
    claude.cleanup();
    npx.cleanup();
    home.cleanup();
  }
});

test("installMotionKit captures failure as 'failed'", () => {
  const claude = makeMockClaude();
  const npx = makeMockNpx({ exit: 1, stderr: "kit boom" });
  const home = makeTmpHome();
  try {
    withMockedPath([claude.dir, npx.dir], () => {
      const result = installMotionKit({ runtime: "claude-code", home: home.dir });
      assert.equal(result.action, "failed");
    });
  } finally {
    claude.cleanup();
    npx.cleanup();
    home.cleanup();
  }
});


// ─── setupFrontendTooling orchestration ─────────────────────────────────


test("setupFrontendTooling never throws and returns both sub-results", async () => {
  const mock = makeMockClaude({ mcpListStdout: "obsidian" });
  const npx = makeMockNpx({ exit: 0 });
  const home = makeTmpHome({ MAGIC_API_KEY: "k" });
  try {
    const result = await withMockedPath([mock.dir, npx.dir], () =>
      setupFrontendTooling({ runtime: "claude-code", home: home.dir }),
    );
    assert.ok(result.magicMcp);
    assert.ok(result.motionKit);
    assert.equal(result.magicMcp.action, "registered");
    assert.equal(result.motionKit.action, "installed");
  } finally {
    mock.cleanup();
    npx.cleanup();
    home.cleanup();
  }
});
