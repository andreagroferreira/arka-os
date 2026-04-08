import { existsSync, readFileSync, writeFileSync, copyFileSync, chmodSync, mkdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ARKAOS_ROOT = resolve(__dirname, "..");
const VERSION = JSON.parse(readFileSync(join(ARKAOS_ROOT, "package.json"), "utf-8")).version;

export async function update() {
  const installDir = join(homedir(), ".arkaos");
  const manifestPath = join(installDir, "install-manifest.json");
  const profilePath = join(installDir, "profile.json");

  if (!existsSync(manifestPath)) {
    console.error("\n  ArkaOS is not installed. Run: npx arkaos install\n");
    process.exit(1);
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const profile = existsSync(profilePath) ? JSON.parse(readFileSync(profilePath, "utf-8")) : {};

  // Check latest version
  let latestVersion = VERSION;
  try {
    latestVersion = execSync("npm view arkaos version 2>/dev/null", { stdio: "pipe" }).toString().trim();
  } catch {}

  console.log(`
  ArkaOS Update
  ─────────────
  Installed: v${manifest.version}
  Package:   v${VERSION}
  Latest:    v${latestVersion}
  `);

  if (manifest.version === latestVersion && manifest.version === VERSION && !process.argv.includes("--force")) {
    console.log("  ✓ Already up to date.\n");
    return;
  }

  console.log("  Updating (keeping your configuration)...\n");

  const pythonCmd = manifest.pythonCmd || "python3";

  // ── 1. Update Python deps ──
  console.log("  [1/6] Updating Python dependencies...");
  try {
    const coreDeps = "pyyaml pydantic rich click jinja2";
    execSync(`${pythonCmd} -m pip install --upgrade ${coreDeps} --quiet`, { stdio: "pipe", timeout: 120000 });
    console.log("         ✓ Core deps updated");

    // Only update optional deps if they were installed before
    try {
      execSync(`${pythonCmd} -c "import fastembed"`, { stdio: "pipe" });
      execSync(`${pythonCmd} -m pip install --upgrade fastembed sqlite-vss --quiet`, { stdio: "pipe", timeout: 180000 });
      console.log("         ✓ Knowledge deps updated");
    } catch { /* not installed, skip */ }

    try {
      execSync(`${pythonCmd} -c "import fastapi"`, { stdio: "pipe" });
      execSync(`${pythonCmd} -m pip install --upgrade fastapi uvicorn --quiet`, { stdio: "pipe", timeout: 60000 });
      console.log("         ✓ Dashboard deps updated");
    } catch { /* not installed, skip */ }

    try {
      execSync(`${pythonCmd} -m pip install -e "${ARKAOS_ROOT}" --quiet`, { stdio: "pipe", timeout: 60000 });
    } catch {}
  } catch (err) {
    console.log(`         ⚠ Some deps failed: ${err.message.slice(0, 80)}`);
  }

  // ── 2. Update config files ──
  console.log("  [2/6] Updating configuration...");
  const constitutionSrc = join(ARKAOS_ROOT, "config", "constitution.yaml");
  if (existsSync(constitutionSrc)) {
    mkdirSync(join(installDir, "config"), { recursive: true });
    copyFileSync(constitutionSrc, join(installDir, "config", "constitution.yaml"));
    console.log("         ✓ Constitution updated");
  }

  // ── 3. Update hooks ──
  console.log("  [3/6] Updating hooks...");
  const hookMap = {
    "user-prompt-submit-v2.sh": "user-prompt-submit.sh",
    "post-tool-use-v2.sh": "post-tool-use.sh",
    "pre-compact-v2.sh": "pre-compact.sh",
  };
  const srcHooksDir = join(ARKAOS_ROOT, "config", "hooks");
  const destHooksDir = join(installDir, "config", "hooks");
  mkdirSync(destHooksDir, { recursive: true });

  for (const [src, dest] of Object.entries(hookMap)) {
    const srcPath = join(srcHooksDir, src);
    const destPath = join(destHooksDir, dest);
    if (existsSync(srcPath)) {
      let content = readFileSync(srcPath, "utf-8");
      content = content.replace(
        /ARKAOS_ROOT="\$\{ARKA_OS:-\$HOME\/\.claude\/skills\/arkaos\}"/g,
        `ARKAOS_ROOT="${ARKAOS_ROOT}"`
      );
      content = content.replace(
        /ARKAOS_HOME="\$\{HOME\}\/\.arkaos"/g,
        `ARKAOS_HOME="${installDir}"`
      );
      writeFileSync(destPath, content);
      try { chmodSync(destPath, 0o755); } catch {}
    }
  }
  console.log("         ✓ Hooks updated");

  // ── 4. Update /arka skill ──
  console.log("  [4/6] Updating /arka skill...");
  const skillSrc = join(ARKAOS_ROOT, "arka", "SKILL.md");
  const skillDest = join(homedir(), ".claude", "skills", "arka");
  mkdirSync(skillDest, { recursive: true });
  if (existsSync(skillSrc)) {
    copyFileSync(skillSrc, join(skillDest, "SKILL.md"));
    writeFileSync(join(skillDest, ".repo-path"), ARKAOS_ROOT);
    writeFileSync(join(skillDest, "VERSION"), VERSION);
    console.log("         ✓ /arka skill updated");
  }

  // ── 5. Update .repo-path ──
  console.log("  [5/6] Updating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  console.log("         ✓ Repo path updated");

  // ── 6. Update manifest ──
  console.log("  [6/6] Finalizing...");
  manifest.version = VERSION;
  manifest.repoRoot = ARKAOS_ROOT;
  manifest.updatedAt = new Date().toISOString();
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log("         ✓ Manifest updated");

  // Reset sync state to trigger /arka update on next session
  const syncStatePath = join(installDir, "sync-state.json");
  const syncState = {
    version: "pending-sync",
    last_sync: null,
    projects_synced: 0,
    skills_synced: 0,
    errors: [],
    core_updated_to: VERSION,
    core_updated_at: new Date().toISOString()
  };
  writeFileSync(syncStatePath, JSON.stringify(syncState, null, 2));
  console.log("         ✓ Sync state reset (run /arka update to sync projects)");

  console.log(`
  ╔══════════════════════════════════════════╗
  ║  ArkaOS updated to v${VERSION}              ║
  ╚══════════════════════════════════════════╝

  Your configuration is preserved:
    Language:  ${profile.language || "not set"}
    Market:    ${profile.market || "not set"}
    Projects:  ${profile.projectsDir || "not set"}
    Vault:     ${profile.vaultPath || "not set"}

  ⚠ Run /arka update in Claude Code to sync all projects.
  `);
}
