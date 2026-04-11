import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, readdirSync, chmodSync, cpSync, statSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { homedir } from "node:os";
import { execSync, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { getRuntimeConfig } from "./detect-runtime.js";
import { findSystemPython, ensureVenv, getArkaosPython, getArkaosPip, pipInstall } from "./python-resolver.js";
import { IS_WINDOWS, HOOK_EXT } from "./platform.js";

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

  // On Unix we deploy the bash wrapper. On Windows we deploy the PowerShell
  // port plus a .cmd shim so `arka-claude ...` works from cmd.exe,
  // PowerShell, and Windows Terminal alike.
  if (IS_WINDOWS) {
    const psSrc  = join(ARKAOS_ROOT, "bin", "arka-claude.ps1");
    const cmdSrc = join(ARKAOS_ROOT, "bin", "arka-claude.cmd");
    let installed = false;
    if (existsSync(psSrc)) {
      copyFileSync(psSrc, join(binDir, "arka-claude.ps1"));
      installed = true;
    }
    if (existsSync(cmdSrc)) {
      copyFileSync(cmdSrc, join(binDir, "arka-claude.cmd"));
      installed = true;
    }
    if (installed) {
      ok("arka-claude wrapper installed (.cmd + .ps1)");
      console.log(`         Add to PATH: setx PATH "%PATH%;%USERPROFILE%\\.arkaos\\bin"`);
      console.log(`         Then reopen any shell and run: arka-claude`);
    }
  } else {
    const wrapperSrc = join(ARKAOS_ROOT, "bin", "arka-claude");
    if (existsSync(wrapperSrc)) {
      copyFileSync(wrapperSrc, join(binDir, "arka-claude"));
      try { chmodSync(join(binDir, "arka-claude"), 0o755); } catch {}
      ok("arka-claude wrapper installed");
      console.log(`         Add to PATH: export PATH="$HOME/.arkaos/bin:$PATH"`);
      console.log(`         Optional alias: alias claude="arka-claude"`);
    }
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
  const verifyHookExt = HOOK_EXT;
  if (existsSync(join(installDir, "config", "hooks", `user-prompt-submit${verifyHookExt}`))) checks++;
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
  // Knowledge + Vector DB - installed individually (see below) so that
  // a failure of one does not block the other.
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

  // Knowledge deps (optional). Installed one package at a time so a
  // partial success (e.g. fastembed OK, sqlite-vec fails on Windows)
  // is reported accurately and the user knows which capability they
  // actually have.
  if (userConfig.installKnowledge !== false) {
    console.log("         Installing knowledge base dependencies...");
    const fastembedOk = pipInstall("fastembed", { log, timeout: 180000 });
    const sqliteVssOk = pipInstall("sqlite-vec", { log, timeout: 180000 });
    if (fastembedOk && sqliteVssOk) {
      ok("Vector DB installed (fastembed, sqlite-vec)");
    } else if (fastembedOk) {
      warn("fastembed installed but sqlite-vec failed — semantic search degraded");
    } else if (sqliteVssOk) {
      warn("sqlite-vec installed but fastembed failed — embedding pipeline degraded");
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

  // Statusline script (platform-aware: .ps1 on Windows, .sh elsewhere)
  const statuslineFile = IS_WINDOWS ? "config/statusline.ps1" : "config/statusline.sh";
  if (existsSync(join(ARKAOS_ROOT, statuslineFile))) {
    files.push([statuslineFile, statuslineFile]);
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

  // On Windows we deploy the PowerShell ports of the hooks; on Unix-like
  // systems we deploy the Bash originals. The adapter in
  // installer/adapters/claude-code.js registers whichever extension was
  // deployed here, so the two lists must stay in sync.
  const hookNames = [
    "session-start",
    "user-prompt-submit",
    "post-tool-use",
    "pre-compact",
    "cwd-changed",
  ];
  const hookExt = HOOK_EXT;

  const srcHooksDir = join(ARKAOS_ROOT, "config", "hooks");

  for (const name of hookNames) {
    const filename = `${name}${hookExt}`;
    const srcPath = join(srcHooksDir, filename);
    const destPath = join(hooksDir, filename);
    if (existsSync(srcPath)) {
      let content = readFileSync(srcPath, "utf-8");
      // The text-replacement pattern below only exists in the legacy
      // bash hooks. Skip it on Windows (.ps1 files resolve ARKAOS_ROOT
      // from the install manifest at runtime instead).
      if (hookExt === ".sh") {
        content = content.replace(
          /ARKAOS_ROOT="\$\{ARKA_OS:-\$HOME\/\.claude\/skills\/arkaos\}"/g,
          `ARKAOS_ROOT="${ARKAOS_ROOT}"`
        );
        content = content.replace(
          /ARKAOS_HOME="\$\{HOME\}\/\.arkaos"/g,
          `ARKAOS_HOME="${installDir}"`
        );
      }
      writeFileSync(destPath, content);
      // chmod is a no-op on Windows (NTFS ACLs aren't POSIX), but the
      // try/catch kept it safe already. Leaving the call in place.
      try { chmodSync(destPath, 0o755); } catch {}
      ok(`Hook: ${filename}`);
    }
  }
}

// Safe directory iteration. Returns an empty array instead of throwing
// when the target does not exist, which lets us skip missing sources
// (fresh repo checkouts may omit optional department resource dirs).
function listSubdirs(parent) {
  if (!existsSync(parent)) return [];
  try {
    return readdirSync(parent, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
  } catch {
    return [];
  }
}

// Port of the "Resources" copy loop from install.sh:399-403. Copies any
// of scripts/references/assets that exist next to a skill's SKILL.md
// into the deployed skill directory. Silent no-op when a resource dir
// does not exist. Each copy is wrapped in a try/catch so a partial
// failure on one resource doesn't block the rest of the deployment.
function copySkillResources(skillSrcDir, skillDestDir) {
  const resources = ["scripts", "references", "assets"];
  for (const res of resources) {
    const src = join(skillSrcDir, res);
    if (!existsSync(src)) continue;
    try {
      cpSync(src, join(skillDestDir, res), { recursive: true });
    } catch {
      // Best-effort — a single missing resource dir shouldn't break install.
    }
  }
}

// Deploy one skill directory as a top-level `arka-<name>/` under the
// Claude Code skills base. Mirrors install.sh lines 396-405 and 414-425.
// Returns true if SKILL.md was deployed, false otherwise.
function deployTopLevelSkill(skillSrcDir, arkaName, skillsBase) {
  const skillMd = join(skillSrcDir, "SKILL.md");
  if (!existsSync(skillMd)) return false;
  const dest = join(skillsBase, arkaName);
  ensureDir(dest);
  copyFileSync(skillMd, join(dest, "SKILL.md"));
  copySkillResources(skillSrcDir, dest);
  return true;
}

function installSkill(config, installDir) {
  // ── Main /arka skill ────────────────────────────────────────────────
  const skillSrc = join(ARKAOS_ROOT, "arka", "SKILL.md");
  const skillsBase = config.skillsDir || join(homedir(), ".claude", "skills");
  const skillDest = join(skillsBase, "arka");

  ensureDir(skillDest);

  if (existsSync(skillSrc)) {
    copyFileSync(skillSrc, join(skillDest, "SKILL.md"));
    writeFileSync(join(skillDest, ".repo-path"), ARKAOS_ROOT);
    writeFileSync(join(skillDest, "VERSION"), VERSION);
    // Nested arka/skills/ (conclave, human-writing) is copied as a
    // reference bundle under the main /arka skill, preserving the
    // old behaviour for anything that reads from that path.
    const nestedSkillsSrc = join(ARKAOS_ROOT, "arka", "skills");
    if (existsSync(nestedSkillsSrc)) {
      const nestedSkillsOut = join(skillDest, "skills");
      ensureDir(nestedSkillsOut);
      try {
        cpSync(nestedSkillsSrc, nestedSkillsOut, { recursive: true });
      } catch {
        // Silent — these are bundled references, not user-facing skills.
      }
    }
    ok("/arka skill installed");
  } else {
    warn("arka/SKILL.md not found in package");
  }

  // ── Department skills ───────────────────────────────────────────────
  // For each `departments/<dept>/SKILL.md`, deploy as top-level
  // `~/.claude/skills/arka-<dept>/`. Mirrors install.sh:391-406, but
  // iterates the source directory dynamically instead of hardcoding a
  // department list (the bash list is stale — ships 8 of the 18 real
  // departments on disk, so half are silently skipped on macOS/Linux
  // too until a user edits install.sh).
  const deptRoot = join(ARKAOS_ROOT, "departments");
  let deptDeployed = 0;
  for (const dept of listSubdirs(deptRoot)) {
    if (deployTopLevelSkill(join(deptRoot, dept), `arka-${dept}`, skillsBase)) {
      deptDeployed++;
    }
  }
  if (deptDeployed > 0) {
    ok(`${deptDeployed} department skills installed (/arka-<dept>)`);
  }

  // ── Sub-skills (departments/*/skills/*) ─────────────────────────────
  // For each `departments/<dept>/skills/<skill>/SKILL.md`, deploy as
  // top-level `~/.claude/skills/arka-<skill>/`. Mirrors install.sh:411-425.
  // Collisions between departments (two depts defining the same
  // sub-skill name) are resolved by "later wins", same semantics as
  // the bash loop — in practice the repo has no collisions today.
  let subSkillDeployed = 0;
  for (const dept of listSubdirs(deptRoot)) {
    const deptSkillsDir = join(deptRoot, dept, "skills");
    for (const subSkill of listSubdirs(deptSkillsDir)) {
      const subSkillSrc = join(deptSkillsDir, subSkill);
      if (deployTopLevelSkill(subSkillSrc, `arka-${subSkill}`, skillsBase)) {
        subSkillDeployed++;
      }
    }
  }
  if (subSkillDeployed > 0) {
    ok(`${subSkillDeployed} sub-skills installed (/arka-<skill>)`);
  }

  // ── Agent personas ──────────────────────────────────────────────────
  // For each `departments/<dept>/agents/<name>.md`, deploy to
  // `~/.claude/agents/arka-<name>.md`. Mirrors install.sh:436-443.
  // The agents dir parallels skillsBase — Claude Code reads it
  // separately from the skills tree.
  const agentsBase = join(homedir(), ".claude", "agents");
  ensureDir(agentsBase);
  let agentDeployed = 0;
  for (const dept of listSubdirs(deptRoot)) {
    const agentsSrc = join(deptRoot, dept, "agents");
    if (!existsSync(agentsSrc)) continue;
    try {
      for (const agentFile of readdirSync(agentsSrc)) {
        if (!agentFile.endsWith(".md")) continue;
        const srcFile = join(agentsSrc, agentFile);
        // Safety: don't deploy anything that's not a regular file.
        try {
          if (!statSync(srcFile).isFile()) continue;
        } catch {
          continue;
        }
        const baseName = agentFile.replace(/\.md$/, "");
        copyFileSync(srcFile, join(agentsBase, `arka-${baseName}.md`));
        agentDeployed++;
      }
    } catch {
      // Silently skip departments with unreadable agents dirs.
    }
  }
  if (agentDeployed > 0) {
    ok(`${agentDeployed} agent personas installed (~/.claude/agents/arka-*.md)`);
  }

  // ── MCP infrastructure ──────────────────────────────────────────────
  // Deploy mcps/ subdirectories (profiles, stacks, scripts) and registry
  // to ~/.claude/skills/arka/mcps/, and the arka-prompts server files to
  // ~/.claude/skills/arka/mcp-server/. Mirrors the mcps/ tree in the repo.
  const mcpsSrc = join(ARKAOS_ROOT, "mcps");
  if (existsSync(mcpsSrc)) {
    const mcpsDest = join(skillDest, "mcps");
    ensureDir(mcpsDest);

    // Copy subdirectories: profiles, stacks, scripts
    for (const subdir of ["profiles", "stacks", "scripts"]) {
      const src = join(mcpsSrc, subdir);
      if (!existsSync(src)) continue;
      const dest = join(mcpsDest, subdir);
      ensureDir(dest);
      try {
        cpSync(src, dest, { recursive: true });
      } catch {}
    }

    // Copy registry.json to mcps root
    const registrySrc = join(mcpsSrc, "registry.json");
    if (existsSync(registrySrc)) {
      copyFileSync(registrySrc, join(mcpsDest, "registry.json"));
    }

    // Make apply-mcps.sh executable
    const applyScript = join(mcpsDest, "scripts", "apply-mcps.sh");
    if (existsSync(applyScript)) {
      try { chmodSync(applyScript, 0o755); } catch {}
    }

    // Deploy arka-prompts server to mcp-server/
    const mcpServerSrc = join(mcpsSrc, "arka-prompts");
    const mcpServerDest = join(skillsBase, "arka", "mcp-server");
    if (existsSync(mcpServerSrc)) {
      ensureDir(mcpServerDest);
      for (const f of ["server.py", "commands.py", "pyproject.toml"]) {
        const src = join(mcpServerSrc, f);
        if (existsSync(src)) copyFileSync(src, join(mcpServerDest, f));
      }
    }

    ok("MCP infrastructure deployed (profiles, stacks, scripts, arka-prompts server)");
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

  // 3. Copy daemon script and core modules it imports
  const daemonSrc = join(arkaosRoot, "bin", "scheduler-daemon.py");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  if (existsSync(daemonSrc)) {
    copyFileSync(daemonSrc, join(binDir, "scheduler-daemon.py"));
    try { chmodSync(join(binDir, "scheduler-daemon.py"), 0o755); } catch {}
    ok("Scheduler daemon deployed");
  }

  // 3b. Copy scheduler core modules so the daemon can import them
  const schedulerModules = [
    "core/cognition/scheduler/__init__.py",
    "core/cognition/scheduler/daemon.py",
    "core/cognition/scheduler/platform.py",
    "core/cognition/scheduler/cli.py",
  ];
  for (const mod of schedulerModules) {
    const src = join(arkaosRoot, mod);
    const dest = join(installDir, mod);
    if (existsSync(src)) {
      ensureDir(dirname(dest));
      copyFileSync(src, dest);
    }
  }
  // Write minimal __init__.py files (don't copy full cognition init — it
  // imports modules not deployed here like capture, insights, memory)
  for (const init of ["core/__init__.py", "core/cognition/__init__.py"]) {
    const dest = join(installDir, init);
    ensureDir(dirname(dest));
    writeFileSync(dest, '"""ArkaOS — deployed subset for scheduler."""\n');
  }
  ok("Scheduler core modules deployed");

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
  const home = homedir();

  // Use the ArkaOS venv Python, not whatever `which python3` finds
  let pythonPath;
  try {
    pythonPath = getArkaosPython();
  } catch {
    try {
      pythonPath = execSync("which python3", { stdio: "pipe" }).toString().trim();
    } catch {
      pythonPath = "python3";
    }
  }

  // PATH must include known Claude CLI locations — launchd inherits a minimal PATH
  const pathValue = `${home}/.local/bin:${home}/.arkaos/bin:/usr/local/bin:/usr/bin:/bin`;

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
\t<key>EnvironmentVariables</key>
\t<dict>
\t\t<key>PATH</key>
\t\t<string>${pathValue}</string>
\t\t<key>HOME</key>
\t\t<string>${home}</string>
\t</dict>
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
  const home = homedir();
  let pythonPath;
  try {
    pythonPath = getArkaosPython();
  } catch {
    try {
      pythonPath = execSync("which python3", { stdio: "pipe" }).toString().trim();
    } catch {
      pythonPath = "python3";
    }
  }

  // systemd inherits a minimal PATH — inject known Claude CLI locations
  const pathValue = `${home}/.local/bin:${home}/.arkaos/bin:/usr/local/bin:/usr/bin:/bin`;

  const serviceDir = join(home, ".config", "systemd", "user");
  const servicePath = join(serviceDir, "arkaos-scheduler.service");
  const unit = `[Unit]
Description=ArkaOS Cognitive Scheduler
After=network.target

[Service]
Type=simple
Environment=PATH=${pathValue}
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

// Recognize the common schtasks failure modes so we can print actionable
// guidance instead of a cryptic "ERROR: Access is denied." Windows
// localizes these strings, so match against both English text and the
// canonical HRESULT code 0x80070005 (E_ACCESSDENIED).
function classifySchtasksError(stderr) {
  const s = (stderr || "").toLowerCase();
  if (s.includes("access is denied") || s.includes("0x80070005") || s.includes("access denied")) {
    return "access-denied";
  }
  if (s.includes("the system cannot find the file") || s.includes("cannot find the path")) {
    return "not-found";
  }
  if (s.includes("already exists")) {
    return "already-exists";
  }
  return "other";
}

function printSchtasksAccessDeniedHelp(pythonPath, daemonPath) {
  // Two realistic root causes on Windows 10/11:
  // 1. Current shell is not elevated AND the local security policy
  //    denies "Log on as a batch job" for the standard Users group
  //    (common on domain-joined or org-managed machines).
  // 2. A previous admin-owned ArkaOS-Scheduler task exists and our
  //    /F overwrite is blocked because the current user can't modify
  //    tasks owned by another principal.
  //
  // Neither case is fatal to the install — the scheduler daemon is a
  // nice-to-have that keeps background tasks ticking. We print the
  // manual registration command so power users can elevate once and
  // run it, and move on.
  console.log("         Access denied. Options:");
  console.log("         1) Re-run the installer from an elevated PowerShell (Run as Administrator)");
  console.log("         2) Or register the task manually from an elevated prompt:");
  console.log(`            schtasks /Create /F /TN "ArkaOS-Scheduler" /SC ONLOGON /TR "\"${pythonPath}\" \"${daemonPath}\""`);
  console.log("         3) Or skip the scheduler and launch the daemon manually when needed:");
  console.log(`            "${pythonPath}" "${daemonPath}"`);
  console.log("         The rest of ArkaOS is installed and functional — this only affects background task automation.");
}

function installSchtasksService(daemonPath) {
  // Prefer the ArkaOS venv python so the scheduled task runs against the
  // interpreter that actually has the ArkaOS core dependencies installed.
  // Falls back to system Python via findSystemPython -> "python" when no
  // venv exists. This replaces `where python3`, which is broken on
  // Windows because the binary is `python.exe`, not `python3.exe`.
  const pythonPath = getArkaosPython() || findSystemPython() || "python";

  // Build the /TR value as a single command line with both paths
  // individually quoted. When schtasks runs the task later, Windows
  // parses this line with CommandLineToArgvW and lifts argv[0] as the
  // executable and argv[1..] as the arguments. Without inner quotes a
  // pythonPath or daemonPath containing spaces would break the parse.
  const trValue = `\"${pythonPath}\" \"${daemonPath}\"`;

  // Use execFileSync (no shell) with an argv array so we bypass cmd.exe
  // quoting rules entirely. Node on Windows handles the argv -> command
  // line encoding, escaping internal quotes with the `\"` convention
  // that CommandLineToArgvW (used by schtasks) understands.
  //
  // /RU with the current username is redundant for a local on-logon
  // task (schtasks defaults to the invoking user), but passing it
  // explicitly makes our intent visible in the XML schtasks writes and
  // surfaces "this task runs as <name>" when a sysadmin audits tasks.
  const currentUser = process.env.USERNAME || process.env.USER || "";
  const createArgs = [
    "/Create", "/F",
    "/TN", "ArkaOS-Scheduler",
    "/SC", "ONLOGON",
    "/TR", trValue,
  ];
  if (currentUser) {
    createArgs.push("/RU", currentUser);
  }
  const runArgs = ["/Run", "/TN", "ArkaOS-Scheduler"];

  const tryRun = (cmd, args) => {
    try {
      execFileSync(cmd, args, { stdio: ["pipe", "pipe", "pipe"] });
      return { ok: true, stderr: "" };
    } catch (err) {
      const raw = err.stderr ? err.stderr.toString() : (err.message || "");
      const stderr = raw.replace(/\r?\n/g, " ").trim();
      return { ok: false, stderr };
    }
  };

  const createResult = tryRun("schtasks", createArgs);
  if (!createResult.ok) {
    const kind = classifySchtasksError(createResult.stderr);
    warn(`Scheduler: schtasks /Create failed (${kind}): ${createResult.stderr.slice(0, 220)}`);
    if (kind === "access-denied") {
      printSchtasksAccessDeniedHelp(pythonPath, daemonPath);
    } else {
      console.log("         Try manually: schtasks /Create /F /TN \"ArkaOS-Scheduler\" /SC ONLOGON /TR \"" + pythonPath + " " + daemonPath + "\"");
    }
    return;
  }

  const runResult = tryRun("schtasks", runArgs);
  if (!runResult.ok) {
    const kind = classifySchtasksError(runResult.stderr);
    warn(`Scheduler: task created but /Run failed (${kind}): ${runResult.stderr.slice(0, 220)}`);
    if (kind === "access-denied") {
      console.log("         Task is registered but couldn't be started now. It will run automatically at next logon.");
    } else {
      console.log("         Task will start at next logon");
    }
    return;
  }

  ok("Scheduler task installed and started (schtasks)");
}

export async function loadAdapter(runtime) {
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
