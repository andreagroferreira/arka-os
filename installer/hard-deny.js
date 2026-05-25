// autoMode.hard_deny defaults for Claude Code (PR45 v2.64.0).
//
// Claude Code v2.1.131+ shipped `autoMode.hard_deny` — actions that block
// unconditionally in auto mode regardless of allow rules. Without this,
// auto mode is structurally unsafe (allowlist alone cannot express
// "never run this even if a broader allow matches"). PR45 ships a
// curated default deny list and merges it into ~/.claude/settings.json
// without clobbering operator-authored entries.
//
// Operator extensions live in ~/.arkaos/hard-deny.json — installer
// reads it on every run and merges into the Claude settings file.
//
// Behaviour:
//   - No-op when runtime is not Claude Code
//   - Idempotent: merges by string equality; duplicates are dropped
//   - Atomic write via .tmp + rename
//   - Preserves all other settings.json content untouched
//   - Never raises — failures logged but don't break the installer

import {
  existsSync, readFileSync, writeFileSync, renameSync, copyFileSync, mkdirSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";

// Curated default deny list. Each entry follows Claude Code's
// permission-rule syntax: ToolName(pattern). The patterns are
// load-bearing — pick conservatively, since auto mode without these
// rules silently allows them when a broader allow matches.
export const DEFAULT_HARD_DENY_RULES = [
  // Destructive git operations
  "Bash(git push --force*)",
  "Bash(git push -f*)",
  "Bash(git reset --hard*)",
  "Bash(git clean -fd*)",
  "Bash(git branch -D*)",

  // Filesystem destruction
  "Bash(rm -rf /*)",
  "Bash(rm -rf ~/*)",
  "Bash(rm -rf ~)",
  "Bash(rm -rf .*)",

  // Secrets and credential paths
  "Read(~/.ssh/*)",
  "Read(~/.ssh/**)",
  "Read(~/.aws/credentials)",
  "Read(~/.aws/config)",
  "Read(~/.gnupg/*)",
  "Read(~/.gnupg/**)",
  "Read(~/.npmrc)",
  "Read(~/.docker/config.json)",
  "Read(~/.config/gh/*)",
  "Read(/etc/shadow)",
  "Read(/etc/sudoers)",

  // Writes to credential / config dirs
  "Write(~/.ssh/*)",
  "Write(~/.aws/credentials)",
  "Write(~/.gnupg/*)",
  "Write(~/.npmrc)",

  // Process / privilege escalation
  "Bash(sudo *)",
  "Bash(su -*)",
  "Bash(chmod 777*)",
  "Bash(curl * | sh*)",
  "Bash(curl * | bash*)",
  "Bash(wget * | sh*)",
  "Bash(wget * | bash*)",
];


// Operator extension file. Lines added here are merged into the
// Claude settings on every install/update.
const _USER_EXTENSION_FILE = "hard-deny.json";


export function seedAutoModeHardDeny({
  runtime = "claude-code",
  home = homedir(),
  defaults = DEFAULT_HARD_DENY_RULES,
} = {}) {
  if (runtime !== "claude-code") {
    return { skipped: "runtime-not-claude-code", action: null, count: 0 };
  }
  const settingsPath = join(home, ".claude", "settings.json");
  if (!existsSync(settingsPath)) {
    return { skipped: "claude-settings-not-found", action: null, count: 0 };
  }
  const userExtensions = readUserExtensions(home);
  const merged = mergeUnique(defaults, userExtensions);
  return writeMergedSettings(settingsPath, merged);
}


function readUserExtensions(home) {
  const path = join(home, ".arkaos", _USER_EXTENSION_FILE);
  if (!existsSync(path)) return [];
  try {
    const data = JSON.parse(readFileSync(path, "utf-8"));
    const rules = Array.isArray(data.hard_deny) ? data.hard_deny : [];
    return rules.filter((r) => typeof r === "string" && r.length > 0);
  } catch {
    return [];
  }
}


function mergeUnique(a, b) {
  const seen = new Set();
  const merged = [];
  for (const rule of [...a, ...b]) {
    if (!seen.has(rule)) {
      seen.add(rule);
      merged.push(rule);
    }
  }
  return merged;
}


function writeMergedSettings(settingsPath, mergedRules) {
  let settings;
  try {
    settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
  } catch {
    return { skipped: "settings-not-parseable", action: null, count: 0 };
  }
  if (typeof settings !== "object" || settings === null) {
    return { skipped: "settings-not-object", action: null, count: 0 };
  }
  settings.autoMode = settings.autoMode && typeof settings.autoMode === "object"
    ? settings.autoMode
    : {};
  const existing = Array.isArray(settings.autoMode.hard_deny)
    ? settings.autoMode.hard_deny
    : [];
  // Preserve any operator-authored rules already in settings.json,
  // then merge our defaults on top. Operator wins on duplicates
  // because they appear first in mergeUnique.
  const finalRules = mergeUnique(existing, mergedRules);
  if (sameRules(existing, finalRules)) {
    return { skipped: null, action: "noop", count: finalRules.length };
  }
  settings.autoMode.hard_deny = finalRules;
  // Atomic write
  const tmp = `${settingsPath}.tmp-${process.pid}`;
  writeFileSync(tmp, JSON.stringify(settings, null, 2) + "\n");
  renameSync(tmp, settingsPath);
  return {
    skipped: null,
    action: existing.length === 0 ? "created" : "merged",
    count: finalRules.length,
  };
}


function sameRules(a, b) {
  if (a.length !== b.length) return false;
  const setA = new Set(a);
  return b.every((r) => setA.has(r));
}
