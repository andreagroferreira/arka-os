// worktree.baseRef default for Claude Code (PR48 v2.67.0).
//
// Claude Code v2.1.151+ added the `worktree.baseRef` setting which
// controls where new worktrees branch from. The default is the repo's
// main branch, but for ArkaOS's iterative feature-branch workflow we
// want worktrees to branch from the current HEAD instead — that way an
// agent working from a feature branch gets a worktree built on top of
// the in-progress branch, not master.
//
// Behaviour:
//   - No-op when runtime is not Claude Code.
//   - Only sets the value when it's missing. Operator-authored values
//     are preserved (this is a default, not a contract).
//   - Atomic write via .tmp + rename.
//   - Never raises — failures are non-fatal.

import { existsSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";


export const DEFAULT_WORKTREE_BASEREF = "head";


export function seedWorktreeBaseRef({
  runtime = "claude-code",
  home = homedir(),
  defaultValue = DEFAULT_WORKTREE_BASEREF,
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
  const existing = settings.worktree && typeof settings.worktree === "object"
    ? settings.worktree
    : null;
  if (existing && typeof existing.baseRef === "string" && existing.baseRef) {
    return { skipped: null, action: "noop", value: existing.baseRef };
  }
  settings.worktree = { ...(existing ?? {}), baseRef: defaultValue };
  const tmp = `${settingsPath}.tmp-${process.pid}`;
  try {
    writeFileSync(tmp, JSON.stringify(settings, null, 2) + "\n");
    renameSync(tmp, settingsPath);
  } catch {
    // Keeps the header's "never raises" claim true inside the module
    // (QG blocker M1 parity, PR1 Interaction Reform).
    return { skipped: "write-failed", action: null };
  }
  return {
    skipped: null,
    action: existing ? "merged" : "created",
    value: defaultValue,
  };
}
