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

// Growth cap, mirroring DEGRADED_LOG_MAX_BYTES in core/hooks/_shared.py
// and ARKA_DEGRADED_MAX_BYTES in _lib/arka_python.sh.
const DEGRADED_MAX_BYTES = 5 * 1024 * 1024;

/**
 * Record that this shim allowed because it could not run, not because it
 * decided — the same JSONL line, in the same file, as record_degraded() in
 * core/hooks/_shared.py and arka_hook_degraded() in _lib/arka_python.sh:
 * {ts,hook,reason,detail}, appended, never on stderr, never fatal, never a
 * change to the exit code.
 *
 * This surface needs it most, not least. On POSIX the installer registers
 * THIS file as the PreToolUse command whenever it and the fastpath engine
 * are deployed (installer/adapters/claude-code.js::hookEntry), so the .sh
 * chain — the one that carries the shell telemetry — is reached only by
 * delegation. Every fail-open below therefore happens BEFORE any other
 * writer exists to observe it: instrumenting only the .sh would have left
 * the default install's three silent exits exactly as silent as before.
 *
 * `via=cjs` leads every detail because `unhandled-fail-open` is a reason
 * the Python entrypoint also emits; the surface has to be readable from
 * the line itself.
 */
function recordDegraded(reason, detail) {
  try {
    const home = process.env.HOME || require("node:os").homedir();
    const dir = path.join(home, ".arkaos", "telemetry");
    const file = path.join(dir, "hook-degraded.jsonl");
    fs.mkdirSync(dir, { recursive: true });
    try {
      if (fs.statSync(file).size >= DEGRADED_MAX_BYTES) {
        fs.renameSync(file, file + ".1");
      }
    } catch {
      // No log yet, or one that cannot be rotated: append regardless. A
      // cap that suppresses the record defeats the point of recording.
    }
    const line = JSON.stringify({
      // Second precision, no fractional part — byte-identical to the
      // strftime/date formats the other two writers use.
      ts: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
      hook: "pre-tool-use",
      reason,
      detail: String(detail == null ? "" : detail)
        // JSON.stringify would escape control characters rather than emit
        // them raw, but a tab-laden stack trace still makes the line
        // unreadable; normalise for the same reason the shell writer does.
        .replace(/[\u0000-\u001f\u007f]/g, " ")
        .slice(0, 400),
    });
    fs.appendFileSync(file, line + "\n");
  } catch {
    // Telemetry must never be the thing that breaks a hook.
  }
}

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
    // A split deploy that lands the .cjs without the .sh disables every
    // gate for the whole install, so this is the highest-stakes silent
    // allow in the file — it never reaches the shell writer.
    recordDegraded("delegate-target-missing", `via=cjs sibling=${sibling}`);
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
    // Two distinct degradations, both invisible until now: bash could not
    // be spawned at all (result.error — no bash on PATH, EACCES, EMFILE),
    // or it was killed by a signal before deciding (status null). Neither
    // is an allow the gate chain ever made.
    const err = result.error;
    recordDegraded(
      "delegate-spawn-failed",
      `via=cjs error=${err ? err.code || err.message : "none"} ` +
        `status=${result.status} signal=${result.signal || "none"}`
    );
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
} catch (err) {
  // The shim's own last resort. Structurally identical to the
  // `unhandled-fail-open` handler at the bottom of core/hooks/
  // pre_tool_use.py, and previously just as silent: exit 0, empty stdout,
  // nothing anywhere to say the gate chain never ran.
  recordDegraded(
    "unhandled-fail-open",
    `via=cjs ${err && err.stack ? err.stack : String(err)}`
  );
  process.exit(FAIL_OPEN_EXIT);
}
