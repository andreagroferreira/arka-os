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
