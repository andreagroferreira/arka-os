import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, readdirSync, chmodSync, cpSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { getRuntimeConfig } from "./detect-runtime.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ARKAOS_ROOT = resolve(__dirname, "..");
const VERSION = JSON.parse(readFileSync(join(ARKAOS_ROOT, "package.json"), "utf-8")).version;

export async function install({ runtime, path, force }) {
  const startTime = Date.now();
  const config = getRuntimeConfig(runtime);
  const installDir = path || join(homedir(), ".arkaos");
  const isUpgrade = existsSync(join(installDir, "install-manifest.json"));

  console.log(`
  ╔══════════════════════════════════════════════════════════╗
  ║  ArkaOS v${VERSION} — The Operating System for AI Agent Teams  ║
  ╚══════════════════════════════════════════════════════════╝

  Runtime:     ${config.name}
  Install dir: ${installDir}
  Mode:        ${isUpgrade ? "Upgrade" : "Fresh install"}
  `);

  // ═══ Step 1: Create directories ═══
  step(1, 12, "Creating directories...");
  ensureDir(installDir);
  const dirs = ["config", "config/hooks", "agents", "media", "session-digests", "vault"];
  for (const d of dirs) ensureDir(join(installDir, d));
  ok(`${dirs.length + 1} directories ready`);

  // ═══ Step 2: Detect v1 installation ═══
  step(2, 12, "Checking for v1 installation...");
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

  // ═══ Step 3: Check Python ═══
  step(3, 12, "Checking Python 3.11+...");
  const pythonCmd = checkPython();
  ok(`Found: ${pythonCmd}`);

  // ═══ Step 4: Install Python core + ALL dependencies ═══
  step(4, 12, "Installing Python dependencies (this may take a minute)...");
  installAllPythonDeps(pythonCmd);

  // ═══ Step 5: Copy configuration files ═══
  step(5, 12, "Copying configuration files...");
  copyConfigFiles(installDir);
  ok("Constitution, standards, and config copied");

  // ═══ Step 6: Install hooks with real paths ═══
  step(6, 12, "Installing hooks...");
  installHooks(installDir);

  // ═══ Step 7: Configure runtime ═══
  step(7, 12, "Configuring runtime...");
  const adapter = await loadAdapter(runtime);
  adapter.configureHooks(config, installDir);
  ok(`${config.name} configured`);

  // ═══ Step 8: Install ArkaOS skill to Claude Code ═══
  step(8, 12, "Installing /arka skill...");
  installSkill(config, installDir);

  // ═══ Step 9: Create references and profile ═══
  step(9, 12, "Creating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  const skillsDir = join(config.skillsDir || join(homedir(), ".claude", "skills"), "arkaos");
  ensureDir(skillsDir);
  writeFileSync(join(skillsDir, ".arkaos-root"), ARKAOS_ROOT);

  const profilePath = join(installDir, "profile.json");
  if (!existsSync(profilePath)) {
    writeFileSync(profilePath, JSON.stringify({
      version: "2",
      created: new Date().toISOString(),
    }, null, 2));
    ok("New profile created");
  } else {
    ok("Existing profile preserved");
  }

  // ═══ Step 10: Index knowledge base (if vault configured) ═══
  step(10, 12, "Checking knowledge base...");
  const kbDb = join(installDir, "knowledge.db");
  if (!existsSync(kbDb)) {
    try {
      execSync(`${pythonCmd} "${join(ARKAOS_ROOT, "scripts", "knowledge-index.py")}" --dir "${join(ARKAOS_ROOT, "departments")}" --db "${kbDb}"`, {
        stdio: "pipe",
        timeout: 60000,
        env: { ...process.env, ARKAOS_ROOT },
      });
      ok("ArkaOS skills indexed into knowledge base");
    } catch {
      warn("Knowledge indexing skipped (run 'npx arkaos index' later)");
    }
  } else {
    ok("Knowledge base already exists");
  }

  // ═══ Step 11: Verify installation ═══
  step(11, 12, "Verifying installation...");
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

  // ═══ Step 12: Finalize ═══
  step(12, 12, "Finalizing...");
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

function checkPython() {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, { stdio: "pipe" }).toString().trim();
      const match = version.match(/(\d+)\.(\d+)/);
      if (match && parseInt(match[1]) >= 3 && parseInt(match[2]) >= 11) {
        return cmd;
      }
    } catch {
      continue;
    }
  }
  console.error(`
  ✗ Python 3.11+ is required but not found.

  Install Python:
    macOS:   brew install python@3.13
    Linux:   sudo apt install python3.13
    Windows: https://python.org/downloads/
  `);
  process.exit(1);
}

function installAllPythonDeps(pythonCmd) {
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

  const allDeps = `${coreDeps} ${knowledgeDeps} ${ingestDeps} ${dashboardDeps}`;

  try {
    // Try uv first (faster)
    try {
      execSync("uv --version", { stdio: "pipe" });
      console.log("         Using uv (fast installer)...");
      execSync(`uv pip install ${allDeps}`, { stdio: "pipe", timeout: 300000 });
      ok("Core + Knowledge + Ingest + Dashboard deps installed");
      // Transcription optional (heavy)
      try {
        execSync(`uv pip install ${transcriptionDeps}`, { stdio: "pipe", timeout: 300000 });
        ok("Whisper transcription installed");
      } catch {
        warn("Whisper not installed (optional — needed for YouTube/audio transcription)");
      }
      return;
    } catch {
      // uv not available, use pip
    }

    console.log("         Installing core dependencies...");
    execSync(`${pythonCmd} -m pip install ${coreDeps} --quiet`, { stdio: "pipe", timeout: 120000 });
    ok("Core deps installed (pyyaml, pydantic, rich, click, jinja2)");

    console.log("         Installing knowledge base dependencies...");
    try {
      execSync(`${pythonCmd} -m pip install ${knowledgeDeps} --quiet`, { stdio: "pipe", timeout: 180000 });
      ok("Vector DB installed (fastembed, sqlite-vss)");
    } catch {
      warn("Vector DB not installed (run: pip install fastembed sqlite-vss)");
    }

    console.log("         Installing content ingest dependencies...");
    try {
      execSync(`${pythonCmd} -m pip install ${ingestDeps} --quiet`, { stdio: "pipe", timeout: 120000 });
      ok("Ingest deps installed (yt-dlp, pdfplumber, beautifulsoup4)");
    } catch {
      warn("Ingest deps not fully installed (some content types may not work)");
    }

    console.log("         Installing dashboard dependencies...");
    try {
      execSync(`${pythonCmd} -m pip install ${dashboardDeps} --quiet`, { stdio: "pipe", timeout: 60000 });
      ok("Dashboard API installed (fastapi, uvicorn)");
    } catch {
      warn("Dashboard API not installed (run: pip install fastapi uvicorn)");
    }

    console.log("         Installing transcription engine...");
    try {
      execSync(`${pythonCmd} -m pip install ${transcriptionDeps} --quiet`, { stdio: "pipe", timeout: 300000 });
      ok("Whisper transcription installed");
    } catch {
      warn("Whisper not installed (optional — needed for YouTube/audio)");
    }

    // Install ArkaOS itself as editable
    try {
      execSync(`${pythonCmd} -m pip install -e "${ARKAOS_ROOT}" --quiet`, { stdio: "pipe", timeout: 60000 });
    } catch {}

  } catch (err) {
    warn(`Some Python deps failed: ${err.message.slice(0, 100)}`);
    console.log("         You can install manually: pip install pyyaml pydantic rich click fastembed sqlite-vss");
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
    "user-prompt-submit-v2.sh": "user-prompt-submit.sh",
    "post-tool-use-v2.sh": "post-tool-use.sh",
    "pre-compact-v2.sh": "pre-compact.sh",
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
