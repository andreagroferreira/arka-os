import { existsSync, readFileSync, writeFileSync, copyFileSync, chmodSync, mkdirSync, readdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { ensureVenv, getArkaosPython, pipInstall } from "./python-resolver.js";
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

  // ── 1. Update Python deps (using venv) ──
  console.log("  [1/8] Updating Python dependencies...");

  // Ensure venv exists (creates one if missing — fixes PEP 668)
  const venvOk = ensureVenv((msg) => console.log(msg));
  if (!venvOk) {
    console.log("         \u26a0 Could not create venv — trying system Python with PEP 668 handling");
  }

  const pythonCmd = getArkaosPython();
  const log = (msg) => console.log(msg);

  // Core deps (always upgrade)
  if (pipInstall("pyyaml pydantic rich click jinja2", { upgrade: true, log })) {
    console.log("         \u2713 Core deps updated");
  } else {
    console.log("         \u26a0 Core deps update failed");
  }

  // Only update optional deps if they were installed before
  const pyCheck = (mod) => {
    try { execSync(`"${pythonCmd}" -c "import ${mod}"`, { stdio: "pipe" }); return true; } catch { return false; }
  };

  if (pyCheck("fastembed")) {
    if (pipInstall("fastembed sqlite-vss", { upgrade: true, log, timeout: 180000 })) {
      console.log("         \u2713 Knowledge deps updated");
    }
  }

  if (pyCheck("fastapi")) {
    if (pipInstall("fastapi uvicorn", { upgrade: true, log, timeout: 60000 })) {
      console.log("         \u2713 Dashboard deps updated");
    }
  }

  // Always install ArkaOS core engine
  if (pipInstall("", { editable: ARKAOS_ROOT, log, timeout: 60000 })) {
    console.log("         \u2713 ArkaOS core engine installed");
  } else {
    console.log("         \u26a0 Core engine install failed — run: npx arkaos doctor");
  }

  // ── 2. Update config files ──
  console.log("  [2/8] Updating configuration...");
  const constitutionSrc = join(ARKAOS_ROOT, "config", "constitution.yaml");
  if (existsSync(constitutionSrc)) {
    mkdirSync(join(installDir, "config"), { recursive: true });
    copyFileSync(constitutionSrc, join(installDir, "config", "constitution.yaml"));
    console.log("         ✓ Constitution updated");
  }

  // ── 3. Update hooks ──
  console.log("  [3/8] Updating hooks...");
  const hookMap = {
    "session-start.sh": "session-start.sh",
    "user-prompt-submit.sh": "user-prompt-submit.sh",
    "post-tool-use.sh": "post-tool-use.sh",
    "pre-compact.sh": "pre-compact.sh",
    "cwd-changed.sh": "cwd-changed.sh",
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

  // ── 4. Update CLI wrapper + user CLAUDE.md ──
  console.log("  [4/8] Updating CLI wrapper and user instructions...");
  const binDir = join(installDir, "bin");
  mkdirSync(binDir, { recursive: true });
  const wrapperSrc = join(ARKAOS_ROOT, "bin", "arka-claude");
  if (existsSync(wrapperSrc)) {
    copyFileSync(wrapperSrc, join(binDir, "arka-claude"));
    try { chmodSync(join(binDir, "arka-claude"), 0o755); } catch {}
    console.log("         ✓ arka-claude wrapper updated");
  }
  const userClaudeMd = join(homedir(), ".claude", "CLAUDE.md");
  const claudeMdSrc = join(ARKAOS_ROOT, "config", "user-claude.md");
  if (existsSync(claudeMdSrc)) {
    mkdirSync(join(homedir(), ".claude"), { recursive: true });
    copyFileSync(claudeMdSrc, userClaudeMd);
    console.log("         ✓ ~/.claude/CLAUDE.md updated");
  }

  // ── 5. Update Cognitive Scheduler ──
  console.log("  [5/8] Updating cognitive scheduler...");
  updateCognitiveScheduler(installDir, ARKAOS_ROOT);

  // ── 6. Update /arka skill ──
  console.log("  [6/8] Updating /arka skill...");
  const skillSrc = join(ARKAOS_ROOT, "arka", "SKILL.md");
  const skillDest = join(homedir(), ".claude", "skills", "arka");
  mkdirSync(skillDest, { recursive: true });
  if (existsSync(skillSrc)) {
    copyFileSync(skillSrc, join(skillDest, "SKILL.md"));
    writeFileSync(join(skillDest, ".repo-path"), ARKAOS_ROOT);
    writeFileSync(join(skillDest, "VERSION"), VERSION);
    console.log("         ✓ /arka skill updated");
  }

  // ── 7. Update .repo-path ──
  console.log("  [7/8] Updating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  console.log("         ✓ Repo path updated");

  // ── 8. Update manifest ──
  console.log("  [8/8] Finalizing...");
  manifest.version = VERSION;
  manifest.repoRoot = ARKAOS_ROOT;
  manifest.pythonCmd = pythonCmd;
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
  console.log("         ✓ Sync state reset (auto-detected on next Claude session)");

  console.log(`
  ╔══════════════════════════════════════════╗
  ║  ArkaOS updated to v${VERSION}              ║
  ╚══════════════════════════════════════════╝

  Your configuration is preserved:
    Language:  ${profile.language || "not set"}
    Market:    ${profile.market || "not set"}
    Projects:  ${profile.projectsDir || "not set"}
    Vault:     ${profile.vaultPath || "not set"}

  Next time you open Claude Code, ArkaOS will automatically
  detect the update and sync all your projects.
  `);
}

function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

function updateCognitiveScheduler(installDir, arkaosRoot) {
  const platform = process.platform;

  // 1. Update schedule config
  const schedSrc = join(arkaosRoot, "config", "cognition", "schedules.yaml");
  if (existsSync(schedSrc)) {
    copyFileSync(schedSrc, join(installDir, "schedules.yaml"));
    console.log("         \u2713 Schedule config updated");
  }

  // 2. Update prompt files
  const promptsDir = join(installDir, "cognition", "prompts");
  ensureDir(promptsDir);
  const promptsSrc = join(arkaosRoot, "config", "cognition", "prompts");
  if (existsSync(promptsSrc)) {
    for (const f of readdirSync(promptsSrc)) {
      copyFileSync(join(promptsSrc, f), join(promptsDir, f));
    }
    console.log("         \u2713 Cognitive prompts updated");
  }

  // 3. Update daemon script
  const daemonSrc = join(arkaosRoot, "bin", "scheduler-daemon.py");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  if (existsSync(daemonSrc)) {
    copyFileSync(daemonSrc, join(binDir, "scheduler-daemon.py"));
    try { chmodSync(join(binDir, "scheduler-daemon.py"), 0o755); } catch {}
    console.log("         \u2713 Scheduler daemon updated");
  }

  // 4. Ensure log directories
  ensureDir(join(installDir, "logs", "dreaming"));
  ensureDir(join(installDir, "logs", "research"));

  // 5. Restart platform service if installed
  const daemonPath = join(binDir, "scheduler-daemon.py");
  if (platform === "darwin") {
    const plistPath = join(homedir(), "Library", "LaunchAgents", "com.arkaos.scheduler.plist");
    if (existsSync(plistPath)) {
      // Reload to pick up updated daemon
      try {
        execSync(`launchctl unload "${plistPath}" 2>/dev/null`, { stdio: "pipe" });
        execSync(`launchctl load "${plistPath}"`, { stdio: "pipe" });
        console.log("         \u2713 Scheduler service restarted (launchd)");
      } catch {
        console.log("         \u26a0 Scheduler reload failed — restart manually");
      }
    } else {
      // First time — install the service
      let pythonPath;
      try {
        pythonPath = execSync("which python3", { stdio: "pipe" }).toString().trim();
      } catch {
        pythonPath = "python3";
      }
      const logDir = join(installDir, "logs");
      const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>Label</key>
\t<string>com.arkaos.scheduler</string>
\t<key>ProgramArguments</key>
\t<array>
\t\t<string>${pythonPath}</string>
\t\t<string>${daemonPath}</string>
\t</array>
\t<key>RunAtLoad</key>
\t<true/>
\t<key>KeepAlive</key>
\t<true/>
\t<key>StandardOutPath</key>
\t<string>${join(logDir, "scheduler-stdout.log")}</string>
\t<key>StandardErrorPath</key>
\t<string>${join(logDir, "scheduler-stderr.log")}</string>
</dict>
</plist>`;
      ensureDir(join(homedir(), "Library", "LaunchAgents"));
      writeFileSync(plistPath, plist);
      try {
        execSync(`launchctl load "${plistPath}"`, { stdio: "pipe" });
        console.log("         \u2713 Scheduler service installed and started (launchd)");
      } catch {
        console.log("         \u26a0 Scheduler plist written but load failed");
      }
    }
  } else if (platform === "linux") {
    try {
      execSync("systemctl --user restart arkaos-scheduler.service 2>/dev/null", { stdio: "pipe" });
      console.log("         \u2713 Scheduler service restarted (systemd)");
    } catch {
      console.log("         \u26a0 Scheduler not running — install with: npx arkaos install");
    }
  }
}
