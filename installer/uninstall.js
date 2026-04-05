import { existsSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export async function uninstall() {
  const installDir = join(homedir(), ".arkaos");

  console.log("\n  ArkaOS Uninstall\n");

  if (!existsSync(installDir)) {
    console.log("  ArkaOS is not installed.");
    return;
  }

  // Remove Claude Code hooks (restore clean settings)
  const settingsPath = join(homedir(), ".claude", "settings.json");
  if (existsSync(settingsPath)) {
    try {
      const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
      delete settings.hooks;
      writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
      console.log("  Removed hooks from Claude Code settings.");
    } catch {
      console.log("  Could not clean Claude Code settings.");
    }
  }

  // Remove install directory
  try {
    rmSync(installDir, { recursive: true, force: true });
    console.log(`  Removed: ${installDir}`);
  } catch (err) {
    console.error(`  Could not remove ${installDir}: ${err.message}`);
  }

  // Remove skills reference
  const skillsRef = join(homedir(), ".claude", "skills", "arkaos");
  if (existsSync(skillsRef)) {
    try {
      rmSync(skillsRef, { recursive: true, force: true });
      console.log(`  Removed: ${skillsRef}`);
    } catch {}
  }

  console.log("\n  ArkaOS uninstalled. Goodbye.\n");
}
