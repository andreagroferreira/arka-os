// ~/.arkaos/config.json seed/migration (PR19 v2.41.0).
//
// Run on every `npx arkaos install` and `npx arkaos@latest update`.
// Idempotent: writes `hooks.hardEnforcement = true` only when the key
// is unset. Explicit user choice (true OR false) is preserved.
//
// Returns a status object:
//   { action: "created" | "added-key" | "noop"
//          | "preserved-user-false" | "rewrote-corrupt" }
// so the installer caller can log a human-readable line per run.

import {
  existsSync, mkdirSync, readFileSync, writeFileSync, renameSync, copyFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";

export function seedArkaosConfig({ home = homedir() } = {}) {
  const cfgPath = join(home, ".arkaos", "config.json");

  if (!existsSync(cfgPath)) {
    writeConfig(cfgPath, { hooks: { hardEnforcement: true } });
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
    writeConfig(cfgPath, { hooks: { hardEnforcement: true } });
    return { action: "rewrote-corrupt", path: cfgPath, backup };
  }

  config.hooks = config.hooks && typeof config.hooks === "object" ? config.hooks : {};
  const current = config.hooks.hardEnforcement;

  if (current === true) {
    return { action: "noop", path: cfgPath };
  }
  if (current === false) {
    return { action: "preserved-user-false", path: cfgPath };
  }

  // Key unset (undefined, null, or any non-boolean) — set to true.
  config.hooks.hardEnforcement = true;
  writeConfig(cfgPath, config);
  return { action: "added-key", path: cfgPath };
}

function writeConfig(cfgPath, payload) {
  mkdirSync(dirname(cfgPath), { recursive: true });
  // Atomic write: render to a sibling .tmp then rename. Prevents partial-write
  // corruption if the process is interrupted between open and close.
  const tmp = `${cfgPath}.tmp-${process.pid}`;
  writeFileSync(tmp, JSON.stringify(payload, null, 2) + "\n");
  renameSync(tmp, cfgPath);
}
