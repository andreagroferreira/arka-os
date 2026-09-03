// fallbackModel default for Claude Code (Runtime Sync PR3).
//
// Claude Code 2.1.166+ reads `fallbackModel` from settings.json: up to
// three models tried in order when the primary model is overloaded or
// unavailable (the runtime de-duplicates and caps the chain at three).
// Without it a single overload or model 404 ends the session — the
// scheduler's nightly cycles died exactly that way. ArkaOS seeds the
// chain Opus 5 → Sonnet 5, the lanes below Fable 5.1 in the Model Fabric.
//
// Behaviour (same contract as worktree-baseref.js):
//   - No-op when runtime is not Claude Code.
//   - Only sets the value when the key is absent or JSON null. An operator
//     chain — an array, an explicit empty array, or the legacy string form
//     — is preserved byte for byte (a default the operator may replace).
//   - Atomic write via .tmp + rename.
//   - Never raises — failures are non-fatal.
//
// core/runtime/claude_code.py:DEFAULT_FALLBACK_MODELS carries the same
// list; tests/python/test_scheduler_daemon.py pins the two to each other.

import { existsSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";


export const DEFAULT_FALLBACK_MODELS = ["claude-opus-5", "claude-sonnet-5"];


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
  if (existing !== undefined && existing !== null) {
    // Present in any non-null shape is the operator's choice: an array, an
    // empty array (chain disabled on purpose) or the legacy single string.
    // JSON null reads as unset (the runtime, drift and the config manager
    // agree), so it is seeded like an absent key.
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
  return { skipped: null, action: "created", value };
}
