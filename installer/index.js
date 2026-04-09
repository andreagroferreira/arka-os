import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, readdirSync, chmodSync, cpSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { getRuntimeConfig } from "./detect-runtime.js";
import { findSystemPython, ensureVenv, getArkaosPython, getArkaosPip, pipInstall } from "./python-resolver.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ARKAOS_ROOT = resolve(__dirname, "..");
const VERSION = JSON.parse(readFileSync(join(ARKAOS_ROOT, "package.json"), "utf-8")).version;

export async function install({ runtime, path, force }) {
  const startTime = Date.now();
  const config = getRuntimeConfig(runtime);
  const isUpgrade = existsSync(join(path || join(homedir(), ".arkaos"), "install-manifest.json"));

  console.log(`
  ╔══════════════════════════════════════════════════════════╗
  ║  ArkaOS v${VERSION} — The Operating System for AI Agent Teams  ║
  ╚══════════════════════════════════════════════════════════╝

  Runtime: ${config.name}
  Mode:    ${isUpgrade ? "Upgrade" : "Fresh install"}
  `);

  // ═══ Interactive Setup ═══
  const { runSetupPrompts } = await import("./prompts.js");
  const userConfig = await runSetupPrompts(isUpgrade);
  const installDir = userConfig.installDir;

  // ═══ Step 1: Create directories ═══
  step(1, 14, "Creating directories...");
  ensureDir(installDir);
  const dirs = ["config", "config/hooks", "agents", "media", "session-digests", "vault"];
  for (const d of dirs) ensureDir(join(installDir, d));
  ok(`${dirs.length + 1} directories ready`);

  // ═══ Step 2: Detect v1 installation ═══
  step(2, 14, "Checking for v1 installation...");
  const v1Paths = [
    join(homedir(), ".claude", "skills", "arka-os"),
    join(homedir(), ".claude", "skills", "arkaos"),
  ];
  const v1Found = v1Paths.find(p => existsSync(p));
  if (v1Found && !existsSync(join(installDir, "migrated-from-v1"))) {
    warn(`v1 detected at ${v1Found}`);
    console.log("         Run 'npx arkaos migrate' after install to migrate your data.");
  } else {
    ok("No v1 installation found");
  }

  // ═══ Step 3: Check Python + create venv ═══
  step(3, 14, "Checking Python 3.11+ and creating virtual environment...");
  const systemPython = findSystemPython();
  if (!systemPython) {
    console.error(`
  ✗ Python 3.11+ is required but not found.

  Install Python:
    macOS:   brew install python@3.13
    Linux:   sudo apt install python3.13
    Windows: https://python.org/downloads/
    `);
    process.exit(1);
  }
  ok(`System Python found: ${systemPython}`);
  const venvCreated = ensureVenv((msg) => console.log(msg));
  if (!venvCreated) {
    warn("Venv creation failed — falling back to system Python (PEP 668 may apply)");
  }
  const pythonCmd = getArkaosPython();
  ok(`ArkaOS Python: ${pythonCmd}`);

  // ═══ Step 4: Install Python core + dependencies based on user choices ═══
  step(4, 14, "Installing Python dependencies (this may take a minute)...");
  installAllPythonDeps(userConfig);

  // ═══ Step 5: Copy configuration files ═══
  step(5, 14, "Copying configuration files...");
  copyConfigFiles(installDir);
  ok("Constitution, standards, and config copied");

  // ═══ Step 6: Install hooks with real paths ═══
  step(6, 14, "Installing hooks...");
  installHooks(installDir);

  // ═══ Step 7: Configure runtime ═══
  step(7, 14, "Configuring runtime...");
  const adapter = await loadAdapter(runtime);
  adapter.configureHooks(config, installDir);
  ok(`${config.name} configured`);

  // ═══ Step 8: Install ArkaOS skill to Claude Code ═══
  step(8, 14, "Installing /arka skill...");
  installSkill(config, installDir);

  // ═══ Step 9: Install CLI wrapper and user instructions ═══
  step(9, 14, "Installing CLI wrapper...");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  const wrapperSrc = join(ARKAOS_ROOT, "bin", "arka-claude");
  if (existsSync(wrapperSrc)) {
    copyFileSync(wrapperSrc, join(binDir, "arka-claude"));
    try { chmodSync(join(binDir, "arka-claude"), 0o755); } catch {}
    ok("arka-claude wrapper installed");
    console.log(`         Add to PATH: export PATH="$HOME/.arkaos/bin:$PATH"`);
    console.log(`         Optional alias: alias claude="arka-claude"`);
  }
  const claudeMdSrc = join(ARKAOS_ROOT, "config", "user-claude.md");
  const userClaudeMd = join(homedir(), ".claude", "CLAUDE.md");
  if (existsSync(claudeMdSrc) && !existsSync(userClaudeMd)) {
    copyFileSync(claudeMdSrc, userClaudeMd);
    ok("~/.claude/CLAUDE.md created (ArkaOS user instructions)");
  } else if (existsSync(userClaudeMd)) {
    ok("~/.claude/CLAUDE.md already exists (preserved)");
  }

  // ═══ Step 10: Deploy Cognitive Scheduler ═══
  step(10, 14, "Deploying cognitive scheduler...");
  deployCognitiveScheduler(installDir, ARKAOS_ROOT);

  // ═══ Step 11: Create references and profile ═══
  step(11, 14, "Creating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  const skillsDir = join(config.skillsDir || join(homedir(), ".claude", "skills"), "arkaos");
  ensureDir(skillsDir);
  writeFileSync(join(skillsDir, ".arkaos-root"), ARKAOS_ROOT);

  const profilePath = join(installDir, "profile.json");
  const profile = {
    version: "2",
    language: userConfig.language,
    market: userConfig.market,
    role: userConfig.role,
    company: userConfig.company,
    projectsDir: userConfig.projectsDir,
    vaultPath: userConfig.vaultPath,
    created: existsSync(profilePath)
      ? JSON.parse(readFileSync(profilePath, "utf-8")).created
      : new Date().toISOString(),
    updated: new Date().toISOString(),
  };
  writeFileSync(profilePath, JSON.stringify(profile, null, 2));
  ok("Profile saved");

  // Save API keys if provided
  if (userConfig.openaiKey || userConfig.googleKey || userConfig.falKey) {
    const keysPath = join(installDir, "keys.json");
    const keys = existsSync(keysPath) ? JSON.parse(readFileSync(keysPath, "utf-8")) : {};
    if (userConfig.openaiKey) keys.OPENAI_API_KEY = userConfig.openaiKey;
    if (userConfig.googleKey) keys.GOOGLE_API_KEY = userConfig.googleKey;
    if (userConfig.falKey) keys.FAL_API_KEY = userConfig.falKey;
    writeFileSync(keysPath, JSON.stringify(keys, null, 2));
    try { chmodSync(keysPath, 0o600); } catch {}
    ok("API keys saved");
  }

  // ═══ Step 12: Index knowledge base ═══
  step(12, 14, "Setting up knowledge base...");
  if (userConfig.installKnowledge) {
    const kbDb = join(installDir, "knowledge.db");
    // Index ArkaOS skills first
    try {
      execSync(`${pythonCmd} "${join(ARKAOS_ROOT, "scripts", "knowledge-index.py")}" --dir "${join(ARKAOS_ROOT, "departments")}" --db "${kbDb}"`, {
        stdio: "pipe", timeout: 60000, env: { ...process.env, ARKAOS_ROOT },
      });
      ok("ArkaOS skills indexed");
    } catch {
      warn("Skill indexing skipped");
    }
    // Index user's Obsidian vault if provided
    if (userConfig.vaultPath && existsSync(userConfig.vaultPath)) {
      try {
        execSync(`${pythonCmd} "${join(ARKAOS_ROOT, "scripts", "knowledge-index.py")}" --vault "${userConfig.vaultPath}" --db "${kbDb}"`, {
          stdio: "pipe", timeout: 120000, env: { ...process.env, ARKAOS_ROOT },
        });
        ok(`Obsidian vault indexed: ${userConfig.vaultPath}`);
      } catch {
        warn("Vault indexing skipped (run 'npx arkaos index' later)");
      }
    }
  } else {
    ok("Knowledge base skipped (install later with 'npx arkaos index')");
  }

  // ═══ Step 13: Verify installation ═══
  step(13, 14, "Verifying installation...");
  let checks = 0;
  if (existsSync(join(installDir, "config", "constitution.yaml"))) checks++;
  if (existsSync(join(installDir, "config", "hooks", "user-prompt-submit.sh"))) checks++;
  if (existsSync(join(installDir, ".repo-path"))) checks++;
  if (existsSync(profilePath)) checks++;
  try {
    execSync(`${pythonCmd} -c "from core.synapse.engine import SynapseEngine; print('ok')"`, {
      stdio: "pipe", cwd: ARKAOS_ROOT, timeout: 10000,
    });
    checks++;
  } catch {}
  ok(`${checks}/5 checks passed`);

  // ═══ Step 14: Finalize ═══
  step(14, 14, "Finalizing...");
  const manifest = {
    version: VERSION,
    runtime,
    installDir,
    repoRoot: ARKAOS_ROOT,
    configDir: config.configDir,
    skillsDir,
    installedAt: new Date().toISOString(),
    pythonCmd,
  };
  writeFileSync(join(installDir, "install-manifest.json"), JSON.stringify(manifest, null, 2));

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log(`
  ╔══════════════════════════════════════════════════════════╗
  ║  ArkaOS v${VERSION} installed successfully! (${elapsed}s)         ║
  ╚══════════════════════════════════════════════════════════╝

  Runtime:     ${config.name}
  Install dir: ${installDir}
  Agents:      65 across 17 departments
  Skills:      244+ backed by enterprise frameworks
  Knowledge:   Vector DB with semantic search
  Dashboard:   Run 'npx arkaos dashboard' to start

  Quick start:
    /arka              — Main orchestrator
    /do <description>  — Natural language routing
    /dev feature       — Development workflow
    /mkt seo-audit     — Marketing audit
    /strat blue-ocean  — Strategy analysis

  Other commands:
    npx arkaos dashboard    — Open monitoring UI
    npx arkaos index        — Index your Obsidian vault
    npx arkaos keys         — Configure API keys
    npx arkaos doctor       — Run health checks
  `);
}

// ═══ Helper Functions ═══

function step(n, total, msg) {
  console.log(`  [${n}/${total}] ${msg}`);
}

function ok(msg) {
  console.log(`         ✓ ${msg}`);
}

function warn(msg) {
  console.log(`         ⚠ ${msg}`);
}

function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

function installAllPythonDeps(userConfig = {}) {
  const log = (msg) => console.log(msg);

  // Core dependencies
  const coreDeps = "pyyaml pydantic rich click jinja2";
  // Knowledge + Vector DB
  const knowledgeDeps = "fastembed sqlite-vss";
  // Ingest (YouTube, PDF, web, audio)
  const ingestDeps = "yt-dlp pdfplumber beautifulsoup4 requests";
  // Dashboard API
  const dashboardDeps = "fastapi uvicorn";
  // Transcription
  const transcriptionDeps = "faster-whisper";

  // Core deps (required)
  console.log("         Installing core dependencies...");
  if (pipInstall(coreDeps, { log })) {
    ok("Core deps installed (pyyaml, pydantic, rich, click, jinja2)");
  } else {
    warn("Core deps failed — some features may not work");
  }

  // Knowledge deps (optional)
  if (userConfig.installKnowledge !== false) {
    console.log("         Installing knowledge base dependencies...");
    if (pipInstall(knowledgeDeps, { log, timeout: 180000 })) {
      ok("Vector DB installed (fastembed, sqlite-vss)");
    } else {
      warn("Vector DB not installed (run later: npx arkaos doctor for fix)");
    }
  }

  // Ingest deps
  console.log("         Installing content ingest dependencies...");
  if (pipInstall(ingestDeps, { log })) {
    ok("Ingest deps installed (yt-dlp, pdfplumber, beautifulsoup4)");
  } else {
    warn("Ingest deps not fully installed (some content types may not work)");
  }

  // Dashboard deps (optional)
  if (userConfig.installDashboard !== false) {
    console.log("         Installing dashboard dependencies...");
    if (pipInstall(dashboardDeps, { log, timeout: 60000 })) {
      ok("Dashboard API installed (fastapi, uvicorn)");
    } else {
      warn("Dashboard API not installed (optional)");
    }
  }

  // Transcription (optional, heavy)
  console.log("         Installing transcription engine...");
  if (pipInstall(transcriptionDeps, { log, timeout: 300000 })) {
    ok("Whisper transcription installed");
  } else {
    warn("Whisper not installed (optional — needed for YouTube/audio)");
  }

  // Install ArkaOS core package as editable
  console.log("         Installing ArkaOS core engine...");
  if (pipInstall("", { editable: ARKAOS_ROOT, log, timeout: 60000 })) {
    ok("ArkaOS core engine installed");
  } else {
    warn("Core engine install failed — run: npx arkaos doctor for fix");
  }
}

function copyConfigFiles(installDir) {
  // Constitution
  const files = [
    ["config/constitution.yaml", "config/constitution.yaml"],
  ];

  // Standards
  const standardsDir = join(ARKAOS_ROOT, "config", "standards");
  if (existsSync(standardsDir)) {
    ensureDir(join(installDir, "config", "standards"));
    for (const f of readdirSync(standardsDir)) {
      files.push([`config/standards/${f}`, `config/standards/${f}`]);
    }
  }

  for (const [src, dest] of files) {
    const srcPath = join(ARKAOS_ROOT, src);
    const destPath = join(installDir, dest);
    if (existsSync(srcPath)) {
      ensureDir(dirname(destPath));
      copyFileSync(srcPath, destPath);
    }
  }
}

function installHooks(installDir) {
  const hooksDir = join(installDir, "config", "hooks");
  ensureDir(hooksDir);

  const hookMap = {
    "session-start.sh": "session-start.sh",
    "user-prompt-submit.sh": "user-prompt-submit.sh",
    "post-tool-use.sh": "post-tool-use.sh",
    "pre-compact.sh": "pre-compact.sh",
    "cwd-changed.sh": "cwd-changed.sh",
  };

  const srcHooksDir = join(ARKAOS_ROOT, "config", "hooks");

  for (const [src, dest] of Object.entries(hookMap)) {
    const srcPath = join(srcHooksDir, src);
    const destPath = join(hooksDir, dest);
    if (existsSync(srcPath)) {
      let content = readFileSync(srcPath, "utf-8");
      // Set ARKAOS_ROOT to the npm package location (persistent)
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
      ok(`Hook: ${dest}`);
    }
  }
}

function installSkill(config, installDir) {
  // Copy arka/SKILL.md to Claude Code skills directory
  const skillSrc = join(ARKAOS_ROOT, "arka", "SKILL.md");
  const skillsBase = config.skillsDir || join(homedir(), ".claude", "skills");
  const skillDest = join(skillsBase, "arka");

  ensureDir(skillDest);

  if (existsSync(skillSrc)) {
    copyFileSync(skillSrc, join(skillDest, "SKILL.md"));
    // Write repo path reference
    writeFileSync(join(skillDest, ".repo-path"), ARKAOS_ROOT);
    writeFileSync(join(skillDest, "VERSION"), VERSION);
    ok("/arka skill installed → Claude Code can now use ArkaOS");
  } else {
    warn("SKILL.md not found in package");
  }

  // Also copy department skills as references
  const deptSkillSrc = join(ARKAOS_ROOT, "arka", "skills");
  if (existsSync(deptSkillSrc)) {
    const skillsOut = join(skillDest, "skills");
    ensureDir(skillsOut);
    try {
      cpSync(deptSkillSrc, skillsOut, { recursive: true });
      ok("Department skills copied");
    } catch {
      // cpSync may not be available in older Node
      warn("Department skills copy skipped");
    }
  }
}

function deployCognitiveScheduler(installDir, arkaosRoot) {
  const platform = process.platform;

  // 1. Copy schedule config
  const schedSrc = join(arkaosRoot, "config", "cognition", "schedules.yaml");
  const schedDest = join(installDir, "schedules.yaml");
  if (existsSync(schedSrc)) {
    copyFileSync(schedSrc, schedDest);
    ok("Schedule config deployed");
  } else {
    warn("schedules.yaml not found in package");
    return;
  }

  // 2. Copy prompt files
  const promptsDir = join(installDir, "cognition", "prompts");
  ensureDir(promptsDir);
  const promptsSrc = join(arkaosRoot, "config", "cognition", "prompts");
  if (existsSync(promptsSrc)) {
    for (const f of readdirSync(promptsSrc)) {
      copyFileSync(join(promptsSrc, f), join(promptsDir, f));
    }
    ok("Cognitive prompts deployed (dreaming, research)");
  }

  // 3. Copy daemon script
  const daemonSrc = join(arkaosRoot, "bin", "scheduler-daemon.py");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  if (existsSync(daemonSrc)) {
    copyFileSync(daemonSrc, join(binDir, "scheduler-daemon.py"));
    try { chmodSync(join(binDir, "scheduler-daemon.py"), 0o755); } catch {}
    ok("Scheduler daemon deployed");
  }

  // 4. Create log directories
  ensureDir(join(installDir, "logs", "dreaming"));
  ensureDir(join(installDir, "logs", "research"));

  // 5. Install platform service
  const daemonPath = join(binDir, "scheduler-daemon.py");
  if (platform === "darwin") {
    installLaunchdService(installDir, daemonPath);
  } else if (platform === "linux") {
    installSystemdService(installDir, daemonPath);
  } else if (platform === "win32") {
    installSchtasksService(daemonPath);
  } else {
    warn(`Scheduler auto-start not supported on ${platform} — run manually`);
  }
}

function installLaunchdService(installDir, daemonPath) {
  const label = "com.arkaos.scheduler";
  const plistDir = join(homedir(), "Library", "LaunchAgents");
  const plistPath = join(plistDir, `${label}.plist`);
  const logDir = join(installDir, "logs");

  let pythonPath;
  try {
    pythonPath = execSync("which python3", { stdio: "pipe" }).toString().trim();
  } catch {
    pythonPath = "python3";
  }

  const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>Label</key>
\t<string>${label}</string>
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

  ensureDir(plistDir);
  // Unload existing if present
  try { execSync(`launchctl unload "${plistPath}" 2>/dev/null`, { stdio: "pipe" }); } catch {}
  writeFileSync(plistPath, plist);
  try {
    execSync(`launchctl load "${plistPath}"`, { stdio: "pipe" });
    ok("Scheduler service installed and started (launchd)");
  } catch {
    warn("Scheduler plist written but launchctl load failed — start manually");
  }
}

function installSystemdService(installDir, daemonPath) {
  let pythonPath;
  try {
    pythonPath = execSync("which python3", { stdio: "pipe" }).toString().trim();
  } catch {
    pythonPath = "python3";
  }

  const serviceDir = join(homedir(), ".config", "systemd", "user");
  const servicePath = join(serviceDir, "arkaos-scheduler.service");
  const unit = `[Unit]
Description=ArkaOS Cognitive Scheduler
After=network.target

[Service]
Type=simple
ExecStart=${pythonPath} ${daemonPath}
Restart=on-failure
RestartSec=60

[Install]
WantedBy=default.target
`;

  ensureDir(serviceDir);
  writeFileSync(servicePath, unit);
  try {
    execSync("systemctl --user enable --now arkaos-scheduler.service", { stdio: "pipe" });
    ok("Scheduler service installed and started (systemd)");
  } catch {
    warn("Scheduler unit written but systemctl enable failed — start manually");
  }
}

function installSchtasksService(daemonPath) {
  let pythonPath;
  try {
    pythonPath = execSync("where python3", { stdio: "pipe" }).toString().trim().split("\n")[0];
  } catch {
    pythonPath = "python";
  }

  try {
    execSync(`schtasks /Create /F /TN "ArkaOS-Scheduler" /SC ONLOGON /TR "${pythonPath} ${daemonPath}"`, { stdio: "pipe" });
    execSync('schtasks /Run /TN "ArkaOS-Scheduler"', { stdio: "pipe" });
    ok("Scheduler task installed and started (schtasks)");
  } catch {
    warn("Scheduler schtasks registration failed — start manually");
  }
}

async function loadAdapter(runtime) {
  try {
    const mod = await import(`./adapters/${runtime}.js`);
    return mod.default;
  } catch {
    return {
      configureHooks(config, installDir) {
        console.log(`         Using generic configuration for ${runtime}`);
      },
    };
  }
}
