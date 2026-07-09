// ArkaOS output style install + default seed (Interaction Reform PR1).
//
// The ArkaOS output style used to exist only as a hand-placed file in
// ~/.claude/output-styles/ — orphaned from the installer, so fresh
// installs never got the branded personality and /config showed the
// generic default. This module makes the repo the source of truth:
//
//   1. Copies config/output-styles/*.md → ~/.claude/output-styles/
//      (always — the file being available is not a preference).
//   2. Seeds `"outputStyle": "ArkaOS"` in ~/.claude/settings.json
//      ONLY when the key is absent. An operator who explicitly chose
//      another style (including "default") is never overridden — the
//      same seed-if-absent contract as worktree-baseref.js and
//      config-seed.js.
//
// Never raises — failures are non-fatal install warnings.

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";


export const DEFAULT_OUTPUT_STYLE = "ArkaOS";


export function installOutputStyles({
  sourceDir,
  home = homedir(),
} = {}) {
  if (!sourceDir || !existsSync(sourceDir)) {
    return { skipped: "source-not-found", copied: 0 };
  }
  try {
    const destDir = join(home, ".claude", "output-styles");
    mkdirSync(destDir, { recursive: true });
    let copied = 0;
    for (const name of readdirSync(sourceDir)) {
      if (!name.endsWith(".md")) continue;
      copyFileSync(join(sourceDir, name), join(destDir, name));
      copied += 1;
    }
    return { skipped: null, copied };
  } catch {
    return { skipped: "copy-failed", copied: 0 };
  }
}


export function seedOutputStyleDefault({
  runtime = "claude-code",
  home = homedir(),
  defaultValue = DEFAULT_OUTPUT_STYLE,
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
  if (typeof settings !== "object" || settings === null) {
    return { skipped: "settings-not-object", action: null };
  }
  if (typeof settings.outputStyle === "string" && settings.outputStyle) {
    return { skipped: null, action: "noop", value: settings.outputStyle };
  }
  settings.outputStyle = defaultValue;
  const tmp = `${settingsPath}.tmp-${process.pid}`;
  try {
    writeFileSync(tmp, JSON.stringify(settings, null, 2) + "\n");
    renameSync(tmp, settingsPath);
  } catch {
    // Read-only ~/.claude, disk full… — "never raises" must be true of
    // THIS module, not delegated to caller try/catch (QG blocker M1).
    return { skipped: "write-failed", action: null };
  }
  return { skipped: null, action: "created", value: defaultValue };
}
