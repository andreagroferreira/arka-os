/**
 * ArkaOS Platform Helpers — single source of truth for platform branching.
 *
 * Centralises the ~19 scattered `process.platform === "win32"` checks into
 * one importable module. Other installer files should import from here
 * instead of inlining platform ternaries.
 */

import { platform } from "node:os";

export const IS_WINDOWS = platform() === "win32";

/** Hook script extension: `.ps1` on Windows, `.sh` elsewhere. */
export const HOOK_EXT = IS_WINDOWS ? ".ps1" : ".sh";

/** Command-line tool to locate executables. */
export const CMD_FINDER = IS_WINDOWS ? "where" : "which";

/** Python binary name (venv resolution is in python-resolver.js). */
export const PYTHON_CMD = IS_WINDOWS ? "python" : "python3";

/**
 * Build the argv for a Node-ecosystem CLI (`npm`, `npx`, `pnpm`, ...) that
 * `spawnSync`/`spawn` can actually execute on every platform.
 *
 * On Windows these tools are `.cmd` shims, which the child_process spawn
 * family cannot launch directly: a bare `"npm"` fails with ENOENT, and an
 * explicit `"npm.cmd"` fails with EINVAL (Node refuses to run batch files
 * without a shell since the CVE-2024-27980 fix). Routing through
 * `cmd.exe /c` keeps the arguments as discrete argv entries, unlike
 * `shell: true`, which concatenates them and triggers DEP0190.
 *
 * Node quotes those entries for `CommandLineToArgvW`, but cmd.exe gets the
 * line FIRST and applies its own rules, so a caret has to be escaped for it
 * explicitly. Measured on Windows 10 / Node 22 with a program that prints
 * its own argv: `impeccable@^3.2` arrives as `impeccable@3.2`, silently
 * narrowing the range from `>=3.2 <4` to `3.2.x`.
 *
 * KNOWN LIMITATION: `& | < > %` are likewise interpreted by cmd.exe and are
 * NOT escaped here — `a&b` arrives as `a` and runs `b`. Every argument this
 * module passes today is a fixed literal without them, so nothing is
 * currently exposed, but do not feed this helper untrusted input.
 *
 * Usage: `const [cmd, argv] = nodeToolCommand("npm", ["install", "-g", pkg]);`
 */
export function nodeToolCommand(tool, args = []) {
  return IS_WINDOWS
    ? ["cmd.exe", ["/c", tool, ...args.map(escapeCaretForCmd)]]
    : [tool, args];
}

/**
 * Double a caret so cmd.exe delivers one — but only when the argument has no
 * whitespace. Node wraps whitespace-bearing arguments in quotes, and inside
 * quotes cmd.exe stops treating `^` as its escape character: doubling there
 * ships a literal `^^` and trades one corruption for another. Measured both
 * ways before this condition was written.
 */
function escapeCaretForCmd(arg) {
  const value = String(arg);
  return /\s/.test(value) ? value : value.replace(/\^/g, "^^");
}
