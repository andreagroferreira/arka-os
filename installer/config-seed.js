// ~/.arkaos/config.json seed/migration (PR19 v2.41.0, extended PR-3 v4.1).
//
// Run on every `npx arkaos install` and `npx arkaos@latest update`.
// Idempotent: seeds each template key only when it is unset. Explicit
// user choice (true OR false) is always preserved.
//
// Seeded template keys (operator decisions):
//   hooks.hardEnforcement = true   (PR19 v2.41.0)
//   hooks.kbFirst         = true   (PR-3 v4.1 — KB-first ON out of the box)
//   memory.sessionMemory  = true   (F1-A2 — session semantic memory ON)
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

function defaultConfig() {
  const config = {};
  for (const [section, keys] of Object.entries(SEEDED_SECTIONS)) {
    config[section] = {};
    for (const key of keys) config[section][key] = true;
  }
  return config;
}

export function seedArkaosConfig({ home = homedir() } = {}) {
  const cfgPath = join(home, ".arkaos", "config.json");

  if (!existsSync(cfgPath)) {
    writeConfig(cfgPath, defaultConfig());
    return { action: "created", path: cfgPath };
  }

  let config;
  try {
    config = JSON.parse(readFileSync(cfgPath, "utf-8"));
    if (typeof config !== "object" || config === null) {
      throw new Error("config root is not an object");
    }
  } catch {
    // Corrupt JSON — keep the broken copy for recovery, write safe default.
    const backup = `${cfgPath}.broken-${Date.now()}`;
    try { copyFileSync(cfgPath, backup); } catch { /* best effort */ }
    writeConfig(cfgPath, defaultConfig());
    return { action: "rewrote-corrupt", path: cfgPath, backup };
  }

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
