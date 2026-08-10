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
 * `cmd.exe /c` keeps every argument individually escaped by Node, unlike
 * `shell: true`, which concatenates them and triggers DEP0190.
 *
 * Usage: `const [cmd, argv] = nodeToolCommand("npm", ["install", "-g", pkg]);`
 */
export function nodeToolCommand(tool, args = []) {
  return IS_WINDOWS ? ["cmd.exe", ["/c", tool, ...args]] : [tool, args];
}
