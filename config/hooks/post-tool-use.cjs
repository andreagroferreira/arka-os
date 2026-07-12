#!/usr/bin/env node
"use strict";
/**
 * ArkaOS — PostToolUse fast-path shim (F2-6).
 *
 * Fast-exits ("{}", exit 0) only when the manifest proves the Python
 * chain would do exactly that with no pending decision-bearing write:
 * benign exit code, no error-trigger in the output, tool outside the
 * stateful set (ExitPlanMode/Task/Agent), and the flow-auth confirm
 * rescan provably redundant (enforcement off, or confirmed auth fresh).
 * MCP usage telemetry — the one write on this path — is replicated
 * inline. Everything else delegates to the sibling post-tool-use.sh.
 *
 * Kill switch: ARKA_HOOK_FASTPATH=0. Fail-open on internal error: try
 * to delegate; if even that fails, print "{}" and exit 0 — the exact
 * degraded form of post-tool-use.sh (NOTE: differs from the PreToolUse
 * fail-open, which is empty stdout).
 */

const fs = require("node:fs");
const path = require("node:path");
const engine = require(path.join(__dirname, "_lib", "fastpath", "engine.cjs"));

function readStdin() {
  try {
    return fs.readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

function failOpen() {
  process.stdout.write("{}\n");
  process.exit(0);
}

function delegate(rawStdin) {
  const sibling = path.join(__dirname, "post-tool-use.sh");
  if (!fs.existsSync(sibling)) {
    // Missing sibling → bash would exit 127; the contract is fail-open
    // with the Post degraded form ("{}").
    failOpen();
  }
  // Lazy require: the fast path never pays for child_process.
  const { spawnSync } = require("node:child_process");
  const result = spawnSync("bash", [sibling], {
    input: rawStdin,
    stdio: ["pipe", "inherit", "inherit"],
    env: { ...process.env, ARKA_HOOK_FASTPATH: "0" },
  });
  if (result.error || result.status === null) {
    failOpen();
  }
  process.exit(result.status);
}

function main() {
  const rawStdin = readStdin();
  if ((process.env.ARKA_HOOK_FASTPATH || "").trim() === "0") {
    delegate(rawStdin);
  }

  let payload;
  try {
    payload = JSON.parse(rawStdin);
  } catch {
    payload = null;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    delegate(rawStdin);
  }

  const manifest = engine.readJsonFile(
    fs, path.join(__dirname, "gate-manifest.json")
  ).data;
  const homeDir = process.env.HOME || require("node:os").homedir();
  const ctx = {
    homeDir,
    env: process.env,
    fs,
    config: engine.readJsonFile(fs, path.join(homeDir, ".arkaos", "config.json")),
  };

  const decision = engine.decidePost(payload, manifest, ctx);
  if (decision.action !== "fast-exit") {
    delegate(rawStdin);
  }

  for (const write of decision.writes) {
    try {
      fs.mkdirSync(path.dirname(write.path), { recursive: true });
      fs.appendFileSync(write.path, write.line, { flag: "a" });
    } catch {
      // Telemetry must never break the hook.
    }
  }
  process.stdout.write(decision.stdout + "\n");
  process.exit(0);
}

try {
  main();
} catch {
  failOpen();
}
