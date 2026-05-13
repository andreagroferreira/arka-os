/**
 * Migration: profile.json schema v2 → v3 (paths-portability, v2.23.0).
 *
 * Adds the structured `projectRoots: string[]` and `reposRoot: string`
 * fields to every existing profile.json so the new path_resolver token
 * substitution can run for the 20K-user installed base.
 *
 * Strategy:
 *   1. Skip if `version === "3"` or `projectRoots` already present (idempotent).
 *   2. Otherwise:
 *        - Write `.bak-<unix-timestamp>` backup beside the profile.
 *        - Parse `projectsDir` free-text to extract absolute paths.
 *        - Default to ["~/Herd","~/Work","~/AIProjects"] if parsing returns 0.
 *        - reposRoot = first match containing "AIProjects", else "~/AIProjects".
 *        - Atomic write (temp file + rename) with version: "3" and migrated_at.
 *        - Log to ~/.arkaos/logs/migrate.log.
 *
 * Safe for concurrent invocations: the backup filename includes the
 * timestamp, atomic rename prevents partial writes, and the idempotent
 * guard means a second run is a no-op.
 *
 * Contract documented in core/specs/SPEC-paths-portability.md (PR1 v2.23.0).
 */

import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const DEFAULT_PROJECT_ROOTS = ["~/Herd", "~/Work", "~/AIProjects"];
const DEFAULT_REPOS_ROOT = "~/AIProjects";

export function migrateProfileSchemaV3({ profilePath, logPath } = {}) {
  const profile = profilePath || join(homedir(), ".arkaos", "profile.json");
  const log = logPath || join(homedir(), ".arkaos", "logs", "migrate.log");

  if (!existsSync(profile)) {
    return { skipped: true, reason: "profile.json absent" };
  }

  let raw;
  try {
    raw = JSON.parse(readFileSync(profile, "utf8"));
  } catch (err) {
    return { skipped: true, reason: `parse error: ${err.message}` };
  }

  if (raw.version === "3" || Array.isArray(raw.projectRoots)) {
    return { skipped: true, reason: "already migrated" };
  }

  const projectRoots = parseProjectsDirText(raw.projectsDir || "");
  const reposRoot =
    projectRoots.find((r) => r.includes("AIProjects")) || DEFAULT_REPOS_ROOT;

  const migrated = {
    ...raw,
    version: "3",
    projectRoots,
    reposRoot,
    migrated_at: new Date().toISOString(),
  };

  const backup = `${profile}.bak-${Math.floor(Date.now() / 1000)}`;
  writeFileSync(backup, readFileSync(profile, "utf8"));

  const tmp = `${profile}.tmp`;
  writeFileSync(tmp, JSON.stringify(migrated, null, 2));
  renameSync(tmp, profile);

  writeLog(log, projectRoots, reposRoot);

  return {
    migrated: true,
    projectRoots,
    reposRoot,
    backup,
  };
}

export function parseProjectsDirText(text) {
  if (!text) return [...DEFAULT_PROJECT_ROOTS];
  const posix = /(?:\/Users|\/home)\/\S+?\/(?:Herd|Work|AIProjects|code|repos)/g;
  const windows = /[A-Z]:\\Users\\[^\s\\]+\\(?:Herd|Work|AIProjects|code|repos)/g;
  const found = [
    ...(text.match(posix) || []),
    ...(text.match(windows) || []),
  ];
  return found.length > 0 ? found : [...DEFAULT_PROJECT_ROOTS];
}

function writeLog(logPath, projectRoots, reposRoot) {
  try {
    mkdirSync(dirname(logPath), { recursive: true });
    const line =
      `[arka:migrated] ${new Date().toISOString()} ` +
      `profile.json schema v2 → v3 (` +
      `${projectRoots.length} roots, reposRoot=${reposRoot})\n`;
    appendFileSync(logPath, line);
  } catch {
    // Log failure should never block migration.
  }
}
