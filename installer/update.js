import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";

export async function update() {
  const installDir = join(homedir(), ".arkaos");
  const manifestPath = join(installDir, "install-manifest.json");

  if (!existsSync(manifestPath)) {
    console.error("  ArkaOS is not installed. Run: npx arkaos install");
    process.exit(1);
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  console.log(`\n  ArkaOS Update — Current: v${manifest.version}\n`);

  const repoRoot = manifest.repoRoot;
  if (!repoRoot || !existsSync(repoRoot)) {
    console.log("  Updating via npm...");
    try {
      execSync("npm update -g arkaos", { stdio: "inherit" });
    } catch {
      console.log("  Reinstalling...");
      execSync("npx arkaos install --force", { stdio: "inherit" });
    }
    return;
  }

  console.log(`  Updating from: ${repoRoot}`);
  try {
    execSync("git pull", { cwd: repoRoot, stdio: "inherit" });
    execSync("npx arkaos install --force", { stdio: "inherit" });
    console.log("\n  Update complete.");
  } catch (err) {
    console.error(`  Update failed: ${err.message}`);
    process.exit(1);
  }
}
