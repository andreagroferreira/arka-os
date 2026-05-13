import { existsSync, mkdirSync, readdirSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import { migrateProfileSchemaV3 } from "./migrations/v3_path_schema.js";

const LEGACY_SKILLS_ROOT = join(homedir(), ".claude", "skills", "arka");
const USER_DATA_ROOT = join(homedir(), ".arkaos");

const LEGACY_PROJECTS = join(LEGACY_SKILLS_ROOT, "projects");
const LEGACY_ECOSYSTEMS = join(LEGACY_SKILLS_ROOT, "knowledge", "ecosystems.json");
const NEW_PROJECTS = join(USER_DATA_ROOT, "projects");
const NEW_ECOSYSTEMS = join(USER_DATA_ROOT, "ecosystems.json");
const LOGS_DIR = join(USER_DATA_ROOT, "logs");

/**
 * Move user-local project descriptors and ecosystems registry from the
 * legacy skill directory to ~/.arkaos/. Idempotent: items already present
 * at the destination are left alone and logged as conflicts.
 *
 * @returns {{ moved: string[], skipped: string[], conflicts: string[], logPath: string|null }}
 */
export function migrateUserData({ dryRun = false } = {}) {
  ensureDataRoot();

  const projectsResult = migrateProjects({ dryRun });
  const ecosystemsResult = migrateEcosystems({ dryRun });

  const moved = [...projectsResult.moved, ...ecosystemsResult.moved];
  const skipped = [...projectsResult.skipped, ...ecosystemsResult.skipped];
  const conflicts = [...projectsResult.conflicts, ...ecosystemsResult.conflicts];

  let profileSchemaResult = null;
  if (!dryRun) {
    try {
      profileSchemaResult = migrateProfileSchemaV3();
      if (profileSchemaResult?.migrated) {
        moved.push(
          `profile.json schema v2 → v3 (${profileSchemaResult.projectRoots.length} roots)`
        );
      }
    } catch (err) {
      conflicts.push(`profile schema v3 migration failed: ${err.message}`);
    }
  }

  const logPath = writeReport({ moved, skipped, conflicts, dryRun });
  return { moved, skipped, conflicts, logPath, profileSchemaResult };
}

export function printMigrationReport(result) {
  const { moved, conflicts, logPath } = result;
  if (moved.length === 0 && conflicts.length === 0) {
    console.log("  ✓ User data already migrated, nothing to move.");
    return;
  }
  console.log(`  ✓ Migration: ${moved.length} moved, ${conflicts.length} conflicts`);
  for (const m of moved) console.log(`    + ${m}`);
  for (const c of conflicts) console.log(`    ! ${c}`);
  if (logPath) console.log(`  Log: ${logPath}`);
}

function ensureDataRoot() {
  if (!existsSync(USER_DATA_ROOT)) mkdirSync(USER_DATA_ROOT, { recursive: true });
  if (!existsSync(NEW_PROJECTS)) mkdirSync(NEW_PROJECTS, { recursive: true });
}

function migrateProjects({ dryRun }) {
  const moved = [];
  const skipped = [];
  const conflicts = [];

  if (!existsSync(LEGACY_PROJECTS) || !statSync(LEGACY_PROJECTS).isDirectory()) {
    skipped.push("projects/: legacy directory absent");
    return { moved, skipped, conflicts };
  }

  for (const entry of readdirSync(LEGACY_PROJECTS)) {
    const src = join(LEGACY_PROJECTS, entry);
    const dst = join(NEW_PROJECTS, entry);
    if (existsSync(dst)) {
      conflicts.push(`projects/${entry}: destination already present, left source untouched`);
      continue;
    }
    if (dryRun) {
      moved.push(`projects/${entry} (dry-run)`);
      continue;
    }
    try {
      renameSync(src, dst);
      moved.push(`projects/${entry}`);
    } catch (err) {
      conflicts.push(`projects/${entry}: ${err.message}`);
    }
  }
  return { moved, skipped, conflicts };
}

function migrateEcosystems({ dryRun }) {
  const moved = [];
  const skipped = [];
  const conflicts = [];

  if (!existsSync(LEGACY_ECOSYSTEMS)) {
    skipped.push("ecosystems.json: legacy file absent");
    return { moved, skipped, conflicts };
  }
  if (existsSync(NEW_ECOSYSTEMS)) {
    conflicts.push("ecosystems.json: destination already present, left source untouched");
    return { moved, skipped, conflicts };
  }
  if (dryRun) {
    moved.push("ecosystems.json (dry-run)");
    return { moved, skipped, conflicts };
  }
  try {
    renameSync(LEGACY_ECOSYSTEMS, NEW_ECOSYSTEMS);
    moved.push("ecosystems.json");
  } catch (err) {
    conflicts.push(`ecosystems.json: ${err.message}`);
  }
  return { moved, skipped, conflicts };
}

function writeReport({ moved, skipped, conflicts, dryRun }) {
  if (moved.length === 0 && conflicts.length === 0) return null;
  if (!existsSync(LOGS_DIR)) mkdirSync(LOGS_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const logPath = join(LOGS_DIR, `migration-${stamp}.log`);
  const body = [
    `ArkaOS user-data migration — ${new Date().toISOString()}`,
    `Source: ${LEGACY_SKILLS_ROOT}`,
    `Destination: ${USER_DATA_ROOT}`,
    `Dry-run: ${dryRun}`,
    "",
    `Moved (${moved.length}):`,
    ...moved.map(m => `  - ${m}`),
    "",
    `Conflicts (${conflicts.length}):`,
    ...conflicts.map(c => `  - ${c}`),
    "",
    `Skipped (${skipped.length}):`,
    ...skipped.map(s => `  - ${s}`),
    "",
  ].join("\n");
  if (!dryRun) writeFileSync(logPath, body);
  return logPath;
}
