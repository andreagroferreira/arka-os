import { existsSync, readFileSync, renameSync, mkdirSync, writeFileSync, cpSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";

const V1_PATHS = {
  skills: join(homedir(), ".claude", "skills", "arka-os"),
  hooks: join(homedir(), ".claude", "settings.json"),
  config: join(homedir(), ".claude", "skills", "arka-os", "config"),
};

const V2_PATH = join(homedir(), ".arkaos");

export async function migrate() {
  console.log(`\n  ArkaOS Migration — v1 → v2\n`);

  // Step 1: Detect v1 installation
  console.log("  [1/5] Detecting v1 installation...");
  const v1Exists = existsSync(V1_PATHS.skills) ||
    existsSync(join(homedir(), ".claude", "skills", "arkaos"));

  if (!v1Exists) {
    // Check alternative v1 paths
    const altPaths = [
      join(homedir(), ".claude", "skills", "arka-os"),
      join(homedir(), ".claude", "skills", "arkaos"),
      join(homedir(), "AIProjects", "arka-os"),
    ];
    const found = altPaths.find(p => existsSync(p));
    if (!found) {
      console.log("  No v1 installation found. Running fresh v2 install...\n");
      execSync("npx arkaos@latest install", { stdio: "inherit" });
      return;
    }
    console.log(`  Found v1 at: ${found}`);
  } else {
    console.log(`  Found v1 at: ${V1_PATHS.skills}`);
  }

  // Step 2: Check for existing v2
  console.log("  [2/5] Checking for existing v2...");
  if (existsSync(V2_PATH)) {
    const manifest = join(V2_PATH, "install-manifest.json");
    if (existsSync(manifest)) {
      const data = JSON.parse(readFileSync(manifest, "utf-8"));
      console.log(`  v2 already installed (v${data.version}). Use 'npx arkaos update' instead.`);
      return;
    }
  }

  // Step 3: Backup v1
  console.log("  [3/5] Backing up v1...");
  const backupDir = join(homedir(), ".arkaos-v1-backup");
  const v1Dir = existsSync(V1_PATHS.skills)
    ? V1_PATHS.skills
    : join(homedir(), ".claude", "skills", "arkaos");

  if (existsSync(v1Dir) && !existsSync(backupDir)) {
    try {
      renameSync(v1Dir, backupDir);
      console.log(`  Backed up to: ${backupDir}`);
    } catch {
      console.log("  Could not backup v1 (may need manual move).");
    }
  } else {
    console.log("  Backup already exists or not needed.");
  }

  // Step 4: Preserve user data
  console.log("  [4/5] Preserving user data...");
  mkdirSync(V2_PATH, { recursive: true });

  // Preserve session digests if they exist
  const v1Digests = join(backupDir, "session-digests");
  const v2Digests = join(V2_PATH, "session-digests");
  if (existsSync(v1Digests) && !existsSync(v2Digests)) {
    try {
      cpSync(v1Digests, v2Digests, { recursive: true });
      console.log("  Preserved session digests.");
    } catch {
      console.log("  Could not copy session digests.");
    }
  }

  // Preserve any Obsidian/knowledge data
  const v1Media = join(backupDir, "media");
  const v2Media = join(V2_PATH, "media");
  if (existsSync(v1Media) && !existsSync(v2Media)) {
    try {
      cpSync(v1Media, v2Media, { recursive: true });
      console.log("  Preserved media files.");
    } catch {
      console.log("  Could not copy media files.");
    }
  }

  // Step 5: Install v2
  console.log("  [5/5] Installing v2...\n");
  try {
    execSync("npx arkaos@latest install --force", { stdio: "inherit" });
  } catch (err) {
    console.error(`\n  Migration failed during install: ${err.message}`);
    console.error(`  Your v1 backup is at: ${backupDir}`);
    const restoreHint = process.platform === "win32"
      ? `Move-Item "${backupDir}" "${v1Dir}"`
      : `mv "${backupDir}" "${v1Dir}"`;
    console.error(`  To restore: ${restoreHint}\n`);
    process.exit(1);
  }

  // Mark as migrated so hook stops alerting
  writeFileSync(join(V2_PATH, "migrated-from-v1"), new Date().toISOString());

  console.log(`
  Migration complete!

  What changed in v2:
  - Install dir: ~/.arkaos (was ~/.claude/skills/arka-os)
  - 62 agents (was 22) across 17 departments (was 9)
  - 238 skills with enterprise frameworks
  - Multi-runtime: Claude Code, Codex, Gemini, Cursor
  - Python core engine (was Bash-only)

  Your v1 backup: ${backupDir}
  You can safely delete it after verifying v2 works.

  Run: npx arkaos doctor    to verify installation.
  `);
}
