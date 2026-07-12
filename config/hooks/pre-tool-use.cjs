#!/usr/bin/env node
"use strict";
/**
 * ArkaOS — PreToolUse fast-path shim (F2-6).
 *
 * An 18ms-p50 Node process (measured; ~10ms of it is bare Node startup)
 * replaces the 82ms-p50 bash->Python chain for the
 * decisions the manifest proves trivial: non-flow-gated tools and
 * discovery Bash with no active budget cap fast-allow here (with the
 * same telemetry appends the Python chain would make); EVERYTHING else
 * delegates to the sibling pre-tool-use.sh, byte-for-byte the current
 * behavior. This shim has no deny path — see engine.cjs invariant #0.
 *
 * Kill switch: ARKA_HOOK_FASTPATH=0 delegates unconditionally (and is
 * re-exported to the child as a recursion guard). Fail-open contract on
 * internal error: try to delegate; if even that fails, exit 0 with
 * empty stdout — identical to pre-tool-use.sh degraded mode.
 */

const fs = require("node:fs");
const path = require("node:path");

const FAIL_OPEN_EXIT = 0;

function readStdin() {
  try {
    return fs.readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

function delegate(rawStdin) {
  const sibling = path.join(__dirname, "pre-tool-use.sh");
  if (!fs.existsSync(sibling)) {
    // Missing sibling → bash would exit 127; the contract is fail-open.
    process.exit(FAIL_OPEN_EXIT);
  }
  // Lazy require: the fast path never pays for child_process.
  const { spawnSync } = require("node:child_process");
  const result = spawnSync("bash", [sibling], {
    input: rawStdin,
    stdio: ["pipe", "inherit", "inherit"],
    env: { ...process.env, ARKA_HOOK_FASTPATH: "0" },
  });
  if (result.error || result.status === null) {
    process.exit(FAIL_OPEN_EXIT);
  }
  process.exit(result.status);
}

function main() {
  const rawStdin = readStdin();
  if ((process.env.ARKA_HOOK_FASTPATH || "").trim() === "0") {
    delegate(rawStdin);
  }
  // QG B3 (redo 1): the engine require lives INSIDE the fail-open
  // boundary — a split deploy (.cjs present, _lib/fastpath absent)
  // must delegate to the sibling .sh, not crash with a stack trace.
  let engine;
  try {
    engine = require(path.join(__dirname, "_lib", "fastpath", "engine.cjs"));
  } catch {
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

  const decision = engine.decidePre(payload, manifest, ctx);
  if (decision.action !== "fast-allow") {
    delegate(rawStdin);
  }

  for (const write of decision.writes) {
    try {
      fs.mkdirSync(path.dirname(write.path), { recursive: true });
      fs.appendFileSync(write.path, write.line, { flag: "a" });
    } catch {
      // Telemetry must never break the hook (same contract as the
      // Python try/except pass around record_telemetry).
    }
  }
  process.exit(0); // allow: empty stdout, exit 0
}

try {
  main();
} catch {
  process.exit(FAIL_OPEN_EXIT);
}
