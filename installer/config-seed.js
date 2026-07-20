// ~/.arkaos/config.json seed/migration (PR19 v2.41.0, extended PR-3 v4.1).
//
// Run on every `npx arkaos install` and `npx arkaos@latest update`.
// Idempotent: seeds each template key only when it is unset. Explicit
// user choice (true OR false) is always preserved.
//
// Seeded template keys (operator decisions):
//   hooks.hardEnforcement       = true   (PR19 v2.41.0)
//   hooks.kbFirst               = true   (PR-3 v4.1 — KB-first ON out of the box)
//   memory.sessionMemory        = true   (F1-A2 — session semantic memory ON)
//   knowledge.graphify.enabled  = true   (graphify HTTP — "active once configured".
//                                          Applies only when a url + token are also
//                                          set; a fresh user with no endpoint is a no-op.)
//
// Returns a status object:
//   { action: "created" | "added-key" | "noop"
//          | "preserved-user-false" | "rewrote-corrupt" }
// so the installer caller can log a human-readable line per run.
// Precedence when several keys differ: created/rewrote-corrupt >
// added-key > preserved-user-false > noop.

import {
  existsSync, mkdirSync, readFileSync, writeFileSync, renameSync, copyFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";

// Template: every listed key seeded to `true` when unset, per section.
const SEEDED_SECTIONS = {
  hooks: ["hardEnforcement", "kbFirst"],
  memory: ["sessionMemory"],
};

// Nested boolean seeds: [section, subsection, key, value]. Same idempotent
// contract as SEEDED_SECTIONS (seed only when unset, preserve explicit
// user choice), but for keys nested two levels deep. graphify.enabled means
// "be active once a url + token exist" — it never activates on its own.
const NESTED_SEEDS = [
  ["knowledge", "graphify", "enabled", true],
];

function defaultConfig() {
  const config = {};
  for (const [section, keys] of Object.entries(SEEDED_SECTIONS)) {
    config[section] = {};
    for (const key of keys) config[section][key] = true;
  }
  for (const [section, sub, key, value] of NESTED_SEEDS) {
    config[section] = config[section] || {};
    config[section][sub] = config[section][sub] || {};
    config[section][sub][key] = value;
  }
  return config;
}

// Seed the one-level keys in SEEDED_SECTIONS: write only when unset, never
// clobber an explicit true/false.
function applyFlatSeeds(config) {
  let added = false;
  let preservedFalse = false;
  for (const [section, keys] of Object.entries(SEEDED_SECTIONS)) {
    const existing = config[section];
    config[section] = existing && typeof existing === "object" ? existing : {};
    for (const key of keys) {
      const current = config[section][key];
      if (current === true) continue;
      if (current === false) {
        preservedFalse = true; // explicit user choice — never overwrite
        continue;
      }
      // Key unset (undefined, null, or any non-boolean) — set to true.
      config[section][key] = true;
      added = true;
    }
  }
  return { added, preservedFalse };
}

// Seed the two-level keys in NESTED_SEEDS, same contract as the flat ones:
// write only when unset, never clobber an explicit true/false.
// Extracted so seedArkaosConfig stays under the 30-line Clean Code limit.
function applyNestedSeeds(config) {
  let added = false;
  let preservedFalse = false;
  for (const [section, sub, key, value] of NESTED_SEEDS) {
    const sec = config[section];
    config[section] = sec && typeof sec === "object" ? sec : {};
    const subObj = config[section][sub];
    config[section][sub] = subObj && typeof subObj === "object" ? subObj : {};
    const current = config[section][sub][key];
    if (current === true || current === false) {
      if (current === false) preservedFalse = true; // explicit user choice
      continue;
    }
    config[section][sub][key] = value;
    added = true;
  }
  return { added, preservedFalse };
}

// Load the config for seeding. Returns {config} when there is something to
// seed, or {done} when the file was absent or corrupt and has been written
// from the template — in which case the caller returns that status as-is.
function loadOrReset(cfgPath) {
  if (!existsSync(cfgPath)) {
    writeConfig(cfgPath, defaultConfig());
    return { done: { action: "created", path: cfgPath } };
  }
  try {
    const config = JSON.parse(readFileSync(cfgPath, "utf-8"));
    if (typeof config !== "object" || config === null) {
      throw new Error("config root is not an object");
    }
    return { config };
  } catch {
    // Corrupt JSON — keep the broken copy for recovery, write safe default.
    const backup = `${cfgPath}.broken-${Date.now()}`;
    try { copyFileSync(cfgPath, backup); } catch { /* best effort */ }
    writeConfig(cfgPath, defaultConfig());
    return { done: { action: "rewrote-corrupt", path: cfgPath, backup } };
  }
}

export function seedArkaosConfig({ home = homedir() } = {}) {
  const cfgPath = join(home, ".arkaos", "config.json");

  const loaded = loadOrReset(cfgPath);
  if (loaded.done) return loaded.done;
  const config = loaded.config;

  const flat = applyFlatSeeds(config);
  const nested = applyNestedSeeds(config);
  const added = flat.added || nested.added;
  const preservedFalse = flat.preservedFalse || nested.preservedFalse;

  if (added) {
    writeConfig(cfgPath, config);
    return { action: "added-key", path: cfgPath };
  }
  if (preservedFalse) {
    return { action: "preserved-user-false", path: cfgPath };
  }
  return { action: "noop", path: cfgPath };
}

function writeConfig(cfgPath, payload) {
  mkdirSync(dirname(cfgPath), { recursive: true });
  // Atomic write: render to a sibling .tmp then rename. Prevents partial-write
  // corruption if the process is interrupted between open and close.
  const tmp = `${cfgPath}.tmp-${process.pid}`;
  writeFileSync(tmp, JSON.stringify(payload, null, 2) + "\n");
  renameSync(tmp, cfgPath);
}
