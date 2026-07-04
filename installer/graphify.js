// Graphify — code knowledge-graph grounding layer for `npx arkaos install`
// and `npx arkaos@latest update`.
//
// Graphify (PyPI package `graphifyy`, CLI `graphify`) extracts a local
// tree-sitter code graph into `<project>/graphify-out/graph.json` with
// EXTRACTED/INFERRED/AMBIGUOUS confidence tags. ArkaOS uses that graph as
// the official grounding layer (Synapse L2.7) so answers about a codebase
// cite real nodes + source locations instead of inventing structure.
//
// Install strategy (best-effort, in order):
//   1. `graphify` already on PATH             → no-op.
//   2. `uv tool install graphifyy`  (preferred)
//   3. `pipx install graphifyy`     (fallback)
//   4. Neither manager available   → print a one-line manual hint.
// Then `graphify install` registers the Graphify skill with AI assistants
// (same best-effort tolerance).
//
// Invariants (.claude/rules/node-installer.md):
//   - ESM, os.homedir()/path.join only, never hardcoded paths.
//   - No interactive prompts; safe in headless/CI runs.
//   - Never throws — the installer must NEVER fail because of Graphify.

import { execSync, spawnSync } from "node:child_process";
import { CMD_FINDER } from "./platform.js";

const PYPI_PACKAGE = "graphifyy"; // double y — the CLI binary is `graphify`
const MANUAL_HINT =
  "Graphify not installed — install manually: uv tool install graphifyy (or pipx install graphifyy)";

function findBinary(name) {
  try {
    const out = execSync(`${CMD_FINDER} ${name}`, {
      stdio: ["ignore", "pipe", "ignore"],
    }).toString().trim().split(/\r?\n/)[0];
    return out || null;
  } catch {
    return null;
  }
}

function readVersion(command) {
  try {
    const out = execSync(command, { stdio: ["ignore", "pipe", "ignore"] }).toString();
    const match = out.match(/(\d+\.\d+(?:\.\d+)?)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

// Try one package-manager install of `graphifyy`. Returns true when the
// child exited 0. Never throws.
function tryInstallVia(manager) {
  const args = manager === "uv" ? ["tool", "install", PYPI_PACKAGE] : ["install", PYPI_PACKAGE];
  const out = spawnSync(manager, args, {
    timeout: 180_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  return !out.error && out.status === 0;
}

// Run `graphify install` so the Graphify skill registers with the AI
// assistant runtimes it detects. Best-effort: failure is reported in the
// status object, never thrown.
function runGraphifySkillInstall() {
  const out = spawnSync("graphify", ["install"], {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  if (out.error || out.status !== 0) {
    const reason = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { action: "failed", reason };
  }
  return { action: "installed" };
}

/**
 * Ensure the Graphify CLI is present and its skill is registered.
 *
 * Returns a status object — never throws, never blocks the install:
 *   { binary: { installed, location?, version?, action, hint? },
 *     skillInstall: { action, reason? } }
 *
 * `options.dryRun` skips installation attempts and `graphify install`.
 */
export function ensureGraphify(options = {}) {
  const result = { binary: null, skillInstall: { action: "skipped", reason: "binary-missing" } };
  try {
    let location = findBinary("graphify");

    if (!location && !options.dryRun) {
      if (findBinary("uv") && tryInstallVia("uv")) {
        location = findBinary("graphify");
      } else if (findBinary("pipx") && tryInstallVia("pipx")) {
        location = findBinary("graphify");
      }
    }

    if (!location) {
      result.binary = {
        installed: false,
        action: options.dryRun ? "dry-run" : "manual-install-needed",
        hint: MANUAL_HINT,
      };
      return result;
    }

    result.binary = {
      installed: true,
      location,
      version: readVersion("graphify --version"),
      action: "present",
    };

    if (options.dryRun) {
      result.skillInstall = { action: "skipped", reason: "dry-run" };
    } else {
      result.skillInstall = runGraphifySkillInstall();
    }
    return result;
  } catch (err) {
    result.binary = result.binary || {
      installed: false,
      action: "check-failed",
      hint: MANUAL_HINT,
    };
    result.skillInstall = { action: "failed", reason: err.message };
    return result;
  }
}

/**
 * Doctor check for installer/doctor.js — is the `graphify` binary present,
 * and at which version? Never throws.
 */
export function graphifyDoctor() {
  try {
    const location = findBinary("graphify");
    if (!location) {
      return { installed: false, location: null, version: null, hint: MANUAL_HINT };
    }
    return {
      installed: true,
      location,
      version: readVersion("graphify --version"),
      hint: null,
    };
  } catch {
    return { installed: false, location: null, version: null, hint: MANUAL_HINT };
  }
}
