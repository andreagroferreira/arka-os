// fallbackModel default for Claude Code (Runtime Sync PR3).
//
// Claude Code 2.1.166+ reads `fallbackModel` from settings.json: up to
// three models tried in order when the primary model is overloaded or
// unavailable (the runtime de-duplicates and caps the chain at three).
// Without it a single overload or model 404 ends the session — the
// scheduler's nightly cycles died exactly that way. ArkaOS seeds the
// chain Opus 5.5 → Sonnet 5, the lanes below Fable 5.1 in the Model Fabric.
//
// Behaviour (same contract as worktree-baseref.js):
//   - No-op when runtime is not Claude Code.
//   - Sets the value when the key is absent or JSON null, and UPGRADES a
//     chain that is exactly a default ArkaOS itself seeded in an earlier
//     release (PREVIOUS_FALLBACK_DEFAULTS). Any other operator chain — an
//     array, an explicit empty array, or the legacy string form — is
//     preserved byte for byte (a default the operator may replace).
//   - Atomic write via .tmp + rename.
//   - Never raises — failures are non-fatal.
//
// core/runtime/claude_code.py carries the same DEFAULT_FALLBACK_MODELS and
// PREVIOUS_FALLBACK_DEFAULTS; tests/python/test_scheduler_daemon.py pins
// the two files to each other.

import { existsSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";


export const DEFAULT_FALLBACK_MODELS = ["claude-opus-5-5", "claude-sonnet-5"];
// Chains ArkaOS itself seeded before — upgraded, not preserved. Append only;
// keep each literal on one line (the Python parity test JSON-parses it).
export const PREVIOUS_FALLBACK_DEFAULTS = [["claude-opus-5", "claude-sonnet-5"]];

function sameChain(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === b.length
    && a.every((id, i) => id === b[i]);
}

function isPreviousDefault(value) {
  return PREVIOUS_FALLBACK_DEFAULTS.some((prev) => sameChain(prev, value));
}


export function seedFallbackModel({
  runtime = "claude-code",
  home = homedir(),
  defaultValue = DEFAULT_FALLBACK_MODELS,
} = {}) {
  if (runtime !== "claude-code") {
    return { skipped: "runtime-not-claude-code", action: null };
  }
  const settingsPath = join(home, ".claude", "settings.json");
  if (!existsSync(settingsPath)) {
    return { skipped: "claude-settings-not-found", action: null };
  }
  let settings;
  try {
    settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
  } catch {
    return { skipped: "settings-not-parseable", action: null };
  }
  if (typeof settings !== "object" || settings === null || Array.isArray(settings)) {
    return { skipped: "settings-not-object", action: null };
  }
  const existing = settings.fallbackModel;
  // A chain equal to a previous ArkaOS default was written by us, not by
  // the operator: it moves to the current default (unless a custom
  // defaultValue already equals it).
  const upgrade = isPreviousDefault(existing) && !sameChain(existing, defaultValue);
  if (existing !== undefined && existing !== null && !upgrade) {
    // Present in any other non-null shape is the operator's choice: an
    // array, an empty array (chain disabled on purpose) or the legacy
    // single string. JSON null reads as unset (the runtime, drift and the
    // config manager agree), so it is seeded like an absent key.
    return { skipped: null, action: "noop", value: existing };
  }
  const value = [...defaultValue];
  settings.fallbackModel = value;
  const tmp = `${settingsPath}.tmp-${process.pid}`;
  try {
    writeFileSync(tmp, JSON.stringify(settings, null, 2) + "\n");
    renameSync(tmp, settingsPath);
  } catch {
    return { skipped: "write-failed", action: null };
  }
  if (upgrade) {
    return { skipped: null, action: "upgraded", value, previous: existing };
  }
  return { skipped: null, action: "created", value };
}
