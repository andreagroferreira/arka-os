import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CURRENT_VERSION = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf-8")).version;

export async function update() {
  const installDir = join(homedir(), ".arkaos");
  const manifestPath = join(installDir, "install-manifest.json");

  if (!existsSync(manifestPath)) {
    console.error("  ArkaOS is not installed. Run: npx arkaos install");
    process.exit(1);
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  console.log(`\n  ArkaOS Update`);
  console.log(`  Installed: v${manifest.version}`);
  console.log(`  Current:   v${CURRENT_VERSION}\n`);

  // Check for latest version on npm
  let latestVersion;
  try {
    latestVersion = execSync("npm view arkaos version 2>/dev/null", { stdio: "pipe" }).toString().trim();
    console.log(`  Latest:    v${latestVersion}`);
  } catch {
    console.log("  Could not check npm for latest version.");
    latestVersion = null;
  }

  if (latestVersion && latestVersion === manifest.version) {
    console.log("\n  Already up to date.");
    return;
  }

  console.log("\n  Updating...");
  try {
    // Clear npx cache and reinstall with latest version
    execSync("npx --yes arkaos@latest install --force", {
      stdio: "inherit",
      env: { ...process.env, npm_config_yes: "true" },
    });
    console.log("\n  Update complete.");
  } catch (err) {
    console.error(`\n  Auto-update failed. Run manually:`);
    console.error(`  npx arkaos@latest install --force\n`);
    process.exit(1);
  }
}
