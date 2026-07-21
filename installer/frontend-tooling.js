// Frontend UI/UX tooling setup for `npx arkaos install` and
// `npx arkaos@latest update`.
//
// Wires three operator-mandated tools into the install/update flow:
//   1. Magic MCP (@21st-dev/magic) — user-scope, API-key gated. The key is
//      prompted interactively when missing and never stored in the repo;
//      it lives only in ~/.arkaos/keys.json (chmod 600) + Claude user config.
//   2. Motion AI Kit (npx motion-ai) — auto-run on every install/update.
//   3. (ui-ux-pro-max plugin + marketplace is handled in claude-plugins.js.)
//
// Invariants (.claude/rules/node-installer.md):
//   - ESM, os.homedir()/path.join only, never hardcoded paths.
//   - No interactive prompts during headless/CI runs (guarded by isTTY).
//   - Never throws — every failure is logged and swallowed so the installer
//     never breaks on optional tooling.

import { existsSync, readFileSync, writeFileSync, chmodSync } from "node:fs";
import { execSync, spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { homedir } from "node:os";
import { join } from "node:path";

const MAGIC_ENV = "MAGIC_API_KEY";

function keysPath(home) {
  return join(home, ".arkaos", "keys.json");
}

function loadKeys(home) {
  const path = keysPath(home);
  if (!existsSync(path)) return {};
  try { return JSON.parse(readFileSync(path, "utf-8")); } catch { return {}; }
}

function saveKey(home, name, value) {
  const path = keysPath(home);
  const keys = loadKeys(home);
  keys[name] = value;
  writeFileSync(path, JSON.stringify(keys, null, 2));
  try { chmodSync(path, 0o600); } catch {}
}

// Resolve the Magic API key from (in order) keys.json, then the environment.
function resolveMagicKey(home) {
  const keys = loadKeys(home);
  return keys[MAGIC_ENV] || process.env[MAGIC_ENV] || "";
}

// Prompt once for the key. Resolves to "" in headless contexts so the
// installer never blocks on a closed stdin (node-installer rule).
function promptMagicKey() {
  if (!process.stdin.isTTY) return Promise.resolve("");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const q = "  21st.dev Magic API key (frontend UI/UX, leave empty to skip): ";
  return new Promise((resolve) => {
    rl.question(q, (answer) => { rl.close(); resolve((answer || "").trim()); });
  });
}

// Ensure MAGIC_API_KEY exists, prompting interactively when missing.
// Returns the resolved key (possibly "").
export async function ensureMagicApiKey({ home = homedir() } = {}) {
  const existing = resolveMagicKey(home);
  if (existing) return existing;
  const entered = await promptMagicKey();
  if (entered) {
    saveKey(home, MAGIC_ENV, entered);
    console.log("         Magic API key saved to ~/.arkaos/keys.json (chmod 600).");
  }
  return entered;
}

function isClaudeCliAvailable() {
  try {
    execSync("claude --version", { stdio: "pipe", timeout: 5000 });
    return true;
  } catch { return false; }
}

function isMagicMcpRegistered() {
  const out = spawnSync("claude", ["mcp", "list"], {
    timeout: 10_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
  });
  return out.status === 0 && /(^|\s)magic(\s|:)/.test(out.stdout || "");
}

// Register the Magic MCP at Claude Code user scope. Idempotent and
// never-throws. Skips on non-Claude runtimes, missing CLI, or missing key.
export function registerMagicMcp({ runtime = "claude-code", apiKey = "" } = {}) {
  if (runtime !== "claude-code") return { action: "skipped", reason: "runtime-not-claude-code" };
  if (!isClaudeCliAvailable()) return { action: "skipped", reason: "claude-cli-not-found" };
  if (!apiKey) return { action: "skipped", reason: "no-api-key" };
  if (isMagicMcpRegistered()) return { action: "already-present" };
  // NOTE (known limitation): the key is passed as a CLI argument because
  // `claude mcp add` offers no stdin/file alternative. It is briefly
  // visible to `ps`/proc while the child runs. It is NEVER written to the
  // repo or to any log (only stderr is captured into `reason`).
  const out = spawnSync("claude", [
    "mcp", "add", "magic", "--scope", "user",
    "--env", `API_KEY=${apiKey}`,
    "--", "npx", "-y", "@21st-dev/magic@latest",
  ], { timeout: 60_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8" });
  if (out.error || out.status !== 0) {
    const reason = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { action: "failed", reason };
  }
  return { action: "registered" };
}

function motionMarkerPath(home) {
  return join(home, ".arkaos", ".motion-kit-installed");
}

// Run the Motion AI Kit. Auto-runs (no prompt) per operator decision
// (2026-05-30), but idempotently: a one-time marker in ~/.arkaos/ means
// re-runs (e.g. every `npx arkaos update`) skip the 180s kit instead of
// re-downloading it. Claude-runtime only, requires the claude CLI (the
// kit installs Motion skills into the Claude agent), never-throws.
export function installMotionKit({ runtime = "claude-code", home = homedir() } = {}) {
  if (runtime !== "claude-code") return { action: "skipped", reason: "runtime-not-claude-code" };
  if (!isClaudeCliAvailable()) return { action: "skipped", reason: "claude-cli-not-found" };
  if (existsSync(motionMarkerPath(home))) return { action: "already-present" };
  const out = spawnSync("npx", ["-y", "motion-ai"], {
    timeout: 180_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
  });
  if (out.error || out.status !== 0) {
    const reason = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { action: "failed", reason };
  }
  try { writeFileSync(motionMarkerPath(home), new Date().toISOString()); } catch {}
  return { action: "installed" };
}

function impeccableMarkerPath(home) {
  return join(home, ".arkaos", ".impeccable-installed");
}

function isImpeccableAvailable() {
  const out = spawnSync("impeccable", ["--version"], {
    timeout: 10_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
  });
  return !out.error && out.status === 0;
}

// Install the impeccable design detector (the deterministic half of the
// design-slop Quality Gate check, core/governance/evidence_checks.py).
// Pinned major (^3.2) — the gate itself never installs (`npx
// --no-install`), so this installer step is the single supply-chain
// entry point. Runtime-agnostic (plain npm CLI), idempotent via marker
// + PATH probe, never-throws.
export function installImpeccableDetector({ home = homedir() } = {}) {
  if (isImpeccableAvailable()) return { action: "already-present" };
  if (existsSync(impeccableMarkerPath(home))) return { action: "already-present" };
  const out = spawnSync("npm", ["install", "-g", "impeccable@^3.2"], {
    timeout: 180_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
  });
  if (out.error || out.status !== 0) {
    const reason = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { action: "failed", reason };
  }
  try { writeFileSync(impeccableMarkerPath(home), new Date().toISOString()); } catch {}
  return { action: "installed" };
}

// Orchestrate the full frontend tooling setup. Single entry point wired
// into both installer/index.js and installer/update.js.
export async function setupFrontendTooling({ runtime = "claude-code", home = homedir() } = {}) {
  const results = {};
  try {
    const apiKey = await ensureMagicApiKey({ home });
    results.magicMcp = registerMagicMcp({ runtime, apiKey });
  } catch (err) {
    results.magicMcp = { action: "failed", reason: err.message };
  }
  try {
    results.motionKit = installMotionKit({ runtime, home });
  } catch (err) {
    results.motionKit = { action: "failed", reason: err.message };
  }
  try {
    results.impeccableDetector = installImpeccableDetector({ home });
  } catch (err) {
    results.impeccableDetector = { action: "failed", reason: err.message };
  }
  return results;
}
