// Process-level tests of the F2-6 fast-path shims: the real .cjs
// entrypoints run as child processes against a sandboxed HOME and a
// stubbed sibling .sh, pinning the I/O contract byte-for-byte
// (empty stdout on Pre allow, "{}" on Post, delegation env guard,
// kill switch, fail-open forms).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync,
  existsSync, cpSync, chmodSync, rmSync,
} from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";

const here = dirname(fileURLToPath(import.meta.url));
const repoHooks = join(here, "..", "..", "config", "hooks");

// Sandbox layout: a copy of the hooks dir whose .sh siblings are stubs
// that record what reached them, plus an isolated HOME.
function makeSandbox({ withManifest = true, shExit = 0 } = {}) {
  const root = mkdtempSync(join(tmpdir(), "arka-fastpath-"));
  const hooks = join(root, "hooks");
  const home = join(root, "home");
  mkdirSync(home, { recursive: true });
  mkdirSync(join(hooks, "_lib", "fastpath"), { recursive: true });
  for (const f of ["pre-tool-use.cjs", "post-tool-use.cjs"]) {
    cpSync(join(repoHooks, f), join(hooks, f));
    chmodSync(join(hooks, f), 0o755);
  }
  cpSync(
    join(repoHooks, "_lib", "fastpath", "engine.cjs"),
    join(hooks, "_lib", "fastpath", "engine.cjs")
  );
  if (withManifest) {
    cpSync(join(repoHooks, "gate-manifest.json"),
      join(hooks, "gate-manifest.json"));
  }
  for (const name of ["pre-tool-use.sh", "post-tool-use.sh"]) {
    const stub = [
      "#!/usr/bin/env bash",
      `cat > "$HOME/delegated-stdin-${name}.txt"`,
      `printf '%s' "\${ARKA_HOOK_FASTPATH:-unset}" > "$HOME/delegated-env-${name}.txt"`,
      name.startsWith("post") ? 'echo \'{"stub":true}\'' : "",
      `exit ${shExit}`,
    ].join("\n");
    writeFileSync(join(hooks, name), stub);
    chmodSync(join(hooks, name), 0o755);
  }
  return { root, hooks, home };
}

function runShim(sandbox, shim, payload, extraEnv = {}) {
  return spawnSync("node", [join(sandbox.hooks, shim)], {
    input: typeof payload === "string" ? payload : JSON.stringify(payload),
    encoding: "utf-8",
    env: {
      PATH: process.env.PATH,
      HOME: sandbox.home,
      ...extraEnv,
    },
  });
}

function readLines(sandbox, rel) {
  const p = join(sandbox.home, rel);
  if (!existsSync(p)) return [];
  return readFileSync(p, "utf-8").trim().split("\n").map((l) => JSON.parse(l));
}

test("P4: non-gated tool fast-allows — exit 0, EMPTY stdout, one kb_first line", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs",
      { tool_name: "Read", session_id: "fp-sid", tool_input: {} });
    assert.equal(r.status, 0);
    assert.equal(r.stdout, "", "Pre allow contract is EMPTY stdout");
    const lines = readLines(sandbox, ".arkaos/telemetry/kb_first.jsonl");
    assert.equal(lines.length, 1);
    assert.equal(lines[0].tool, "Read");
    assert.equal(lines[0].reason, "tool-not-gated");
    assert.ok(!existsSync(join(sandbox.home, "delegated-stdin-pre-tool-use.sh.txt")),
      "must not delegate");
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("P5: discovery Bash fast-allows with kb_first + enforcement lines", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs", {
      tool_name: "Bash", session_id: "fp-sid", cwd: "/w",
      tool_input: { command: "git status" },
    });
    assert.equal(r.status, 0);
    assert.equal(r.stdout, "");
    assert.equal(
      readLines(sandbox, ".arkaos/telemetry/kb_first.jsonl").length, 1);
    const enforcement =
      readLines(sandbox, ".arkaos/telemetry/enforcement.jsonl");
    assert.equal(enforcement.length, 1);
    assert.equal(enforcement[0].cwd, "/w");
    assert.equal(enforcement[0].reason, "tool-not-gated");
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("delegation: Write reaches the .sh with stdin intact, recursion guard set, ZERO shim telemetry", () => {
  const sandbox = makeSandbox();
  try {
    const payload = { tool_name: "Write", session_id: "fp-sid",
      tool_input: { file_path: "/x" } };
    const r = runShim(sandbox, "pre-tool-use.cjs", payload);
    assert.equal(r.status, 0);
    const forwarded = readFileSync(
      join(sandbox.home, "delegated-stdin-pre-tool-use.sh.txt"), "utf-8");
    assert.deepEqual(JSON.parse(forwarded), payload);
    assert.equal(readFileSync(
      join(sandbox.home, "delegated-env-pre-tool-use.sh.txt"), "utf-8"), "0",
      "child must carry ARKA_HOOK_FASTPATH=0");
    assert.equal(
      readLines(sandbox, ".arkaos/telemetry/kb_first.jsonl").length, 0,
      "no double-log: Python owns telemetry on delegation");
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("delegation mirrors the .sh exit code (deny=2 passes through)", () => {
  const sandbox = makeSandbox({ shExit: 2 });
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs",
      { tool_name: "Write", session_id: "fp-sid", tool_input: {} });
    assert.equal(r.status, 2, "a Python deny must survive the shim");
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("kill switch: ARKA_HOOK_FASTPATH=0 delegates even a P4 tool", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs",
      { tool_name: "Read", session_id: "fp-sid", tool_input: {} },
      { ARKA_HOOK_FASTPATH: "0" });
    assert.equal(r.status, 0);
    assert.ok(existsSync(
      join(sandbox.home, "delegated-stdin-pre-tool-use.sh.txt")));
    assert.equal(
      readLines(sandbox, ".arkaos/telemetry/kb_first.jsonl").length, 0);
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("missing manifest: everything delegates (no fast path without proof)", () => {
  const sandbox = makeSandbox({ withManifest: false });
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs",
      { tool_name: "Read", session_id: "fp-sid", tool_input: {} });
    assert.equal(r.status, 0);
    assert.ok(existsSync(
      join(sandbox.home, "delegated-stdin-pre-tool-use.sh.txt")));
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("corrupt stdin delegates; with the .sh also broken it fails open per event", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "pre-tool-use.cjs", "{not json");
    assert.equal(r.status, 0, "corrupt stdin → .sh stub handles it");

    // Break the siblings: Pre fails open with EMPTY stdout + exit 0,
    // Post with "{}" + exit 0 — the two distinct degraded forms.
    rmSync(join(sandbox.hooks, "pre-tool-use.sh"));
    rmSync(join(sandbox.hooks, "post-tool-use.sh"));
    const pre = runShim(sandbox, "pre-tool-use.cjs", "{not json");
    assert.equal(pre.status, 0);
    assert.equal(pre.stdout, "");
    const post = runShim(sandbox, "post-tool-use.cjs", "{not json");
    assert.equal(post.status, 0);
    assert.equal(post.stdout.trim(), "{}");
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("Q6: benign MCP call fast-exits '{}' and appends mcp-usage", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "post-tool-use.cjs", {
      tool_name: "mcp__obsidian__search_notes", session_id: "fp-sid",
      exit_code: "0", tool_output: "3 notes",
    });
    assert.equal(r.status, 0);
    assert.equal(r.stdout.trim(), "{}");
    const lines = readLines(sandbox, ".arkaos/telemetry/mcp-usage.jsonl");
    assert.equal(lines.length, 1);
    assert.equal(lines[0].server, "obsidian");
    assert.ok(!existsSync(
      join(sandbox.home, "delegated-stdin-post-tool-use.sh.txt")));
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("Q7: hard enforcement without fresh auth delegates to Python", () => {
  const sandbox = makeSandbox();
  try {
    mkdirSync(join(sandbox.home, ".arkaos"), { recursive: true });
    writeFileSync(join(sandbox.home, ".arkaos", "config.json"),
      JSON.stringify({ hooks: { hardEnforcement: true } }));
    const authDir = join(sandbox.root, "flow-auth");
    mkdirSync(authDir);
    const r = runShim(sandbox, "post-tool-use.cjs", {
      tool_name: "Read", session_id: "fp-sid",
      exit_code: "0", tool_output: "ok",
    }, { ARKA_FLOW_AUTH_DIR: authDir });
    assert.equal(r.status, 0);
    assert.ok(existsSync(
      join(sandbox.home, "delegated-stdin-post-tool-use.sh.txt")),
      "confirm rescan is load-bearing here — must delegate");

    // Fresh auth flips it to fast-exit.
    writeFileSync(join(authDir, "fp-sid.json"), JSON.stringify({
      marker_type: "routing", confirmed_ts: Date.now() / 1000 - 30,
    }));
    rmSync(join(sandbox.home, "delegated-stdin-post-tool-use.sh.txt"));
    const fresh = runShim(sandbox, "post-tool-use.cjs", {
      tool_name: "Read", session_id: "fp-sid",
      exit_code: "0", tool_output: "ok",
    }, { ARKA_FLOW_AUTH_DIR: authDir });
    assert.equal(fresh.status, 0);
    assert.equal(fresh.stdout.trim(), "{}");
    assert.ok(!existsSync(
      join(sandbox.home, "delegated-stdin-post-tool-use.sh.txt")));
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});

test("Post error output delegates (gotchas pipeline is Python's)", () => {
  const sandbox = makeSandbox();
  try {
    const r = runShim(sandbox, "post-tool-use.cjs", {
      tool_name: "Bash", session_id: "fp-sid",
      exit_code: "0", tool_output: "fatal: not a git repository",
    });
    assert.equal(r.status, 0);
    assert.equal(r.stdout.trim(), '{"stub":true}');
  } finally {
    rmSync(sandbox.root, { recursive: true, force: true });
  }
});
