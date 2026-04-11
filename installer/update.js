import { existsSync, readFileSync, writeFileSync, copyFileSync, chmodSync, mkdirSync, readdirSync, cpSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { ensureVenv, getArkaosPython, pipInstall } from "./python-resolver.js";
import { getRuntimeConfig } from "./detect-runtime.js";
import { loadAdapter } from "./index.js";
import { IS_WINDOWS, HOOK_EXT } from "./platform.js";
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

  // ── Legacy path migration ──────────────────────────────────────────────
  // Older v2 hooks wrote their state (gotchas, hook metrics, session
  // digests) into `~/.arka-os/` — the v1 path — instead of the canonical
  // v2 runtime directory `~/.arkaos/`. Post-fix the hooks now write to
  // `.arkaos`, so any existing data in `.arka-os` needs to be migrated
  // forward on the next update. We COPY (not move) because v1 tooling
  // such as `bin/arka*` and the kb/ scripts also read from `.arka-os`
  // and must keep working during co-existence; the migrate command
  // remains the way to do a destructive v1 -> v2 cutover.
  try {
    migrateLegacyHookState(homedir(), installDir);
  } catch (err) {
    console.log(`         \u26a0 Legacy hook state migration skipped: ${err.message}`);
  }

  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const profile = existsSync(profilePath) ? JSON.parse(readFileSync(profilePath, "utf-8")) : {};

  // Check latest version
  let latestVersion = VERSION;
  try {
    // stderr is suppressed via stdio: "ignore" rather than `2>/dev/null`
    // so the command works under cmd.exe on Windows just as well as bash.
    latestVersion = execSync("npm view arkaos version", {
      stdio: ["pipe", "pipe", "ignore"],
    }).toString().trim();
  } catch {}

  console.log(`
  ArkaOS Update
  ─────────────
  Installed: v${manifest.version}
  Package:   v${VERSION}
  Latest:    v${latestVersion}
  `);

  // Dev-checkout detection: when ArkaOS is being run from a local git
  // clone (as opposed to a published `npx arkaos@latest` install), the
  // version number in package.json is a poor signal of whether there's
  // anything to re-deploy. A contributor working on a feature branch
  // can have 20+ commits of real code changes with the version string
  // still at the last release — every `npx arkaos@file:. update` would
  // refuse to run with a misleading "already up to date" message.
  //
  // Signal: ARKAOS_ROOT is a dev checkout iff it contains a `.git/`
  // directory. A published npm package never ships `.git/`; a local
  // `git clone` always has it. This is robust across install methods
  // (npx cache, local file path, global install) because none of them
  // preserve `.git` in their extraction, but a bare clone always does.
  //
  // When detected, we skip the version-equality gate entirely and
  // always run the full update sequence. Published installs still get
  // the happy-path "already up to date" when the version matches.
  const isDevCheckout = existsSync(join(ARKAOS_ROOT, ".git"));
  const versionsMatch = manifest.version === latestVersion && manifest.version === VERSION;
  const forceRequested = process.argv.includes("--force");

  if (versionsMatch && !forceRequested && !isDevCheckout) {
    console.log("  ✓ Already up to date.\n");
    return;
  }

  if (isDevCheckout && versionsMatch && !forceRequested) {
    console.log("  ℹ Dev checkout detected — running update even though version matches.\n");
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

  // Knowledge deps (fastembed + sqlite-vec) are upgraded one-at-a-time
  // so a failure of one cannot drag the other down with it.
  if (pyCheck("fastembed")) {
    const fastembedOk = pipInstall("fastembed", { upgrade: true, log, timeout: 180000 });
    const sqliteVssOk = pipInstall("sqlite-vec", { upgrade: true, log, timeout: 180000 });
    if (fastembedOk && sqliteVssOk) {
      console.log("         \u2713 Knowledge deps updated (fastembed, sqlite-vec)");
    } else if (fastembedOk) {
      console.log("         \u26a0 fastembed upgraded but sqlite-vec failed \u2014 semantic search degraded");
    } else if (sqliteVssOk) {
      console.log("         \u26a0 sqlite-vec upgraded but fastembed failed \u2014 embedding pipeline degraded");
    } else {
      console.log("         \u26a0 Knowledge deps upgrade failed \u2014 run: npx arkaos doctor");
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
  mkdirSync(join(installDir, "config"), { recursive: true });
  if (existsSync(constitutionSrc)) {
    copyFileSync(constitutionSrc, join(installDir, "config", "constitution.yaml"));
    console.log("         ✓ Constitution updated");
  }
  const statuslineFile = IS_WINDOWS ? "statusline.ps1" : "statusline.sh";
  const statuslineSrc = join(ARKAOS_ROOT, "config", statuslineFile);
  if (existsSync(statuslineSrc)) {
    copyFileSync(statuslineSrc, join(installDir, "config", statuslineFile));
    console.log("         ✓ Statusline updated");
  }

  // ── 3. Update hooks ──
  console.log("  [3/8] Updating hooks...");
  // Keep this list in lockstep with installer/index.js::installHooks and
  // installer/adapters/claude-code.js::hookCommand. Platform-aware: .ps1
  // on Windows, .sh everywhere else.
  const hookNames = [
    "session-start",
    "user-prompt-submit",
    "post-tool-use",
    "pre-compact",
    "cwd-changed",
  ];
  const hookExt = HOOK_EXT;
  const srcHooksDir = join(ARKAOS_ROOT, "config", "hooks");
  const destHooksDir = join(installDir, "config", "hooks");
  mkdirSync(destHooksDir, { recursive: true });

  for (const name of hookNames) {
    const filename = `${name}${hookExt}`;
    const srcPath = join(srcHooksDir, filename);
    const destPath = join(destHooksDir, filename);
    if (existsSync(srcPath)) {
      let content = readFileSync(srcPath, "utf-8");
      // Legacy ARKAOS_ROOT/ARKAOS_HOME text injection only applies to
      // the bash hooks; the PowerShell ports resolve paths at runtime
      // from the install manifest.
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
      try { chmodSync(destPath, 0o755); } catch {}
    }
  }
  console.log("         ✓ Hook scripts updated");

  // Re-register hooks in the runtime's settings file.
  // Without this, updating from an older version leaves settings.json
  // frozen at the previous hook spec (missing new hooks, stale timeouts).
  // Safe on all platforms: identical to the call init.js makes on fresh
  // install, which is already validated on macOS and Linux.
  try {
    const runtimeId = manifest.runtime || "claude-code";
    const runtimeConfig = getRuntimeConfig(runtimeId);
    if (runtimeConfig) {
      const adapter = await loadAdapter(runtimeId);
      adapter.configureHooks(runtimeConfig, installDir);
      console.log("         ✓ Hooks re-registered in settings");
    }
  } catch (err) {
    console.log(`         ⚠ Could not re-register hooks: ${err.message}`);
  }

  // ── 4. Update CLI wrapper + user CLAUDE.md ──
  console.log("  [4/8] Updating CLI wrapper and user instructions...");
  const binDir = join(installDir, "bin");
  mkdirSync(binDir, { recursive: true });

  // Platform-aware: bash wrapper on Unix; .ps1 + .cmd shim on Windows.
  if (IS_WINDOWS) {
    const psSrc  = join(ARKAOS_ROOT, "bin", "arka-claude.ps1");
    const cmdSrc = join(ARKAOS_ROOT, "bin", "arka-claude.cmd");
    if (existsSync(psSrc))  copyFileSync(psSrc,  join(binDir, "arka-claude.ps1"));
    if (existsSync(cmdSrc)) copyFileSync(cmdSrc, join(binDir, "arka-claude.cmd"));
    if (existsSync(psSrc) || existsSync(cmdSrc)) {
      console.log("         ✓ arka-claude wrapper updated (.cmd + .ps1)");
    }
  } else {
    const wrapperSrc = join(ARKAOS_ROOT, "bin", "arka-claude");
    if (existsSync(wrapperSrc)) {
      copyFileSync(wrapperSrc, join(binDir, "arka-claude"));
      try { chmodSync(join(binDir, "arka-claude"), 0o755); } catch {}
      console.log("         ✓ arka-claude wrapper updated");
    }
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

  // ── 6. Update /arka skill + department skills + sub-skills + agents ──
  // Mirrors the full deployment in installer/index.js::installSkill so
  // that `npx arkaos update` re-deploys the same surface area a fresh
  // install creates. Before this change, update.js only refreshed the
  // main `/arka` skill, so any department skill (arka-dev, arka-brand,
  // etc.) or sub-skill (arka-code-review, arka-viral, etc.) or agent
  // persona added after the original install was silently missing on
  // upgrade. Discovered during ClientAdvisory's bake-in: 233 top-level arka-*
  // skills on his WSL (deployed long ago by install.sh) vs 1 skill on
  // his Windows install (only the main /arka). The Node installer
  // never deployed anything else.
  console.log("  [6/8] Updating /arka skill...");
  const skillsBase = join(homedir(), ".claude", "skills");
  const skillSrc = join(ARKAOS_ROOT, "arka", "SKILL.md");
  const skillDest = join(skillsBase, "arka");
  mkdirSync(skillDest, { recursive: true });
  if (existsSync(skillSrc)) {
    copyFileSync(skillSrc, join(skillDest, "SKILL.md"));
    writeFileSync(join(skillDest, ".repo-path"), ARKAOS_ROOT);
    writeFileSync(join(skillDest, "VERSION"), VERSION);
    console.log("         ✓ /arka skill updated");
  }

  // Department skills + sub-skills + agent personas.
  // Keep in sync with installer/index.js::installSkill — if anything
  // changes about how top-level skills or agents are structured, both
  // functions must be updated together.
  const listSubdirs = (parent) => {
    if (!existsSync(parent)) return [];
    try {
      return readdirSync(parent, { withFileTypes: true })
        .filter((e) => e.isDirectory())
        .map((e) => e.name);
    } catch {
      return [];
    }
  };
  const copyResources = (src, dest) => {
    for (const res of ["scripts", "references", "assets"]) {
      const s = join(src, res);
      if (!existsSync(s)) continue;
      try { cpSync(s, join(dest, res), { recursive: true }); } catch {}
    }
  };
  const deployTop = (src, arkaName) => {
    const md = join(src, "SKILL.md");
    if (!existsSync(md)) return false;
    const dest = join(skillsBase, arkaName);
    mkdirSync(dest, { recursive: true });
    copyFileSync(md, join(dest, "SKILL.md"));
    copyResources(src, dest);
    return true;
  };

  const deptRoot = join(ARKAOS_ROOT, "departments");
  let deptCount = 0;
  let subCount = 0;
  for (const dept of listSubdirs(deptRoot)) {
    if (deployTop(join(deptRoot, dept), `arka-${dept}`)) deptCount++;
    for (const sub of listSubdirs(join(deptRoot, dept, "skills"))) {
      if (deployTop(join(deptRoot, dept, "skills", sub), `arka-${sub}`)) subCount++;
    }
  }
  if (deptCount > 0) {
    console.log(`         ✓ ${deptCount} department skills updated`);
  }
  if (subCount > 0) {
    console.log(`         ✓ ${subCount} sub-skills updated`);
  }

  const agentsBase = join(homedir(), ".claude", "agents");
  mkdirSync(agentsBase, { recursive: true });
  let agentCount = 0;
  for (const dept of listSubdirs(deptRoot)) {
    const agentsSrc = join(deptRoot, dept, "agents");
    if (!existsSync(agentsSrc)) continue;
    try {
      for (const file of readdirSync(agentsSrc)) {
        if (!file.endsWith(".md")) continue;
        const srcFile = join(agentsSrc, file);
        try { if (!statSync(srcFile).isFile()) continue; } catch { continue; }
        const base = file.replace(/\.md$/, "");
        copyFileSync(srcFile, join(agentsBase, `arka-${base}.md`));
        agentCount++;
      }
    } catch {}
  }
  if (agentCount > 0) {
    console.log(`         ✓ ${agentCount} agent personas updated`);
  }

  // MCP infrastructure: deploy mcps/ subdirectories, registry, and
  // arka-prompts server — mirrors the same block in installSkill().
  const mcpsSrc = join(ARKAOS_ROOT, "mcps");
  if (existsSync(mcpsSrc)) {
    const mcpsDest = join(skillDest, "mcps");
    if (!existsSync(mcpsDest)) mkdirSync(mcpsDest, { recursive: true });

    for (const subdir of ["profiles", "stacks", "scripts"]) {
      const src = join(mcpsSrc, subdir);
      if (!existsSync(src)) continue;
      const dest = join(mcpsDest, subdir);
      if (!existsSync(dest)) mkdirSync(dest, { recursive: true });
      try { cpSync(src, dest, { recursive: true }); } catch {}
    }

    const registrySrc = join(mcpsSrc, "registry.json");
    if (existsSync(registrySrc)) {
      copyFileSync(registrySrc, join(mcpsDest, "registry.json"));
    }

    const applyScript = join(mcpsDest, "scripts", "apply-mcps.sh");
    if (existsSync(applyScript)) {
      try { chmodSync(applyScript, 0o755); } catch {}
    }

    const mcpServerSrc = join(mcpsSrc, "arka-prompts");
    const mcpServerDest = join(skillsBase, "arka", "mcp-server");
    if (existsSync(mcpServerSrc)) {
      if (!existsSync(mcpServerDest)) mkdirSync(mcpServerDest, { recursive: true });
      for (const f of ["server.py", "commands.py", "pyproject.toml"]) {
        const src = join(mcpServerSrc, f);
        if (existsSync(src)) copyFileSync(src, join(mcpServerDest, f));
      }
    }

    console.log("         ✓ MCP infrastructure updated (profiles, stacks, scripts, arka-prompts server)");
  }

  // ── 6b. Copy feature registry for sync engine ──
  const featuresSource = join(ARKAOS_ROOT, 'core', 'sync', 'features');
  const featuresDest = join(installDir, 'config', 'sync', 'features');
  if (existsSync(featuresSource)) {
    mkdirSync(featuresDest, { recursive: true });
    const featureFiles = readdirSync(featuresSource).filter(f => f.endsWith('.yaml'));
    for (const file of featureFiles) {
      copyFileSync(join(featuresSource, file), join(featuresDest, file));
    }
    if (featureFiles.length > 0) {
      console.log(`         ✓ Feature registry: ${featureFiles.length} features copied`);
    }
  }

  // ── 7. Update .repo-path + .arkaos-root ──
  // Two references point at the source repo. Both MUST be updated on
  // every update pass, otherwise running `npx arkaos update` from a
  // new source directory leaves one file still pointing at the old
  // location and the hooks get confused about which repo to read
  // VERSION from.
  //
  // - `~/.arkaos/.repo-path`: read by session-start.ps1 / .sh to
  //   find the VERSION file for the drift banner.
  // - `~/.claude/skills/arkaos/.arkaos-root`: used by the skills
  //   alias to locate the source repo root from inside Claude Code.
  //
  // installer/index.js writes both in step 11 of the fresh install
  // flow; update.js previously only wrote the first, which is a
  // latent bug that surfaces any time a user runs update from a
  // different clone than the original install.
  console.log("  [7/8] Updating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  const skillsArkaosDir = join(homedir(), ".claude", "skills", "arkaos");
  if (existsSync(skillsArkaosDir)) {
    writeFileSync(join(skillsArkaosDir, ".arkaos-root"), ARKAOS_ROOT);
    console.log("         ✓ Repo path + skills alias updated");
  } else {
    // Fresh install never ran (or user deleted the skills alias);
    // don't recreate it here — that's the install flow's job.
    console.log("         ✓ Repo path updated (skills alias not present)");
  }

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

/**
 * Copy v2 hook state files from the legacy ~/.arka-os/ directory into
 * the canonical ~/.arkaos/ runtime directory. Safe to run every update:
 * - If ~/.arka-os/ does not exist, does nothing.
 * - If a destination file already exists and is non-empty, it is NOT
 *   overwritten (user data wins).
 * - Source files are left in place so that v1 tooling (bin/arka*, the
 *   kb/ scripts, and `arkaos migrate`) keeps working during
 *   coexistence. A destructive cleanup happens only via
 *   `arkaos migrate` which is the documented one-way cutover.
 *
 * State migrated: gotchas.json, hook-metrics.json, session-digests/*.md.
 * Everything else in ~/.arka-os/ (v1 profile, capabilities, kb-jobs,
 * env file, media, pro content, ...) is intentionally ignored.
 */
function migrateLegacyHookState(homeDir, installDir) {
  const legacyDir = join(homeDir, ".arka-os");
  if (!existsSync(legacyDir)) return;

  const targetDir = installDir;
  ensureDir(targetDir);

  let migrated = 0;

  // Simple files: only copy if the target is missing or empty.
  for (const name of ["gotchas.json", "hook-metrics.json"]) {
    const src = join(legacyDir, name);
    if (!existsSync(src)) continue;
    const dst = join(targetDir, name);
    let dstEmpty = true;
    if (existsSync(dst)) {
      try {
        const content = readFileSync(dst, "utf-8").trim();
        dstEmpty = content.length === 0 || content === "[]" || content === "{}";
      } catch {
        dstEmpty = true;
      }
    }
    if (dstEmpty) {
      try {
        copyFileSync(src, dst);
        migrated++;
      } catch {}
    }
  }

  // Session digests: copy each .md file that isn't already present in
  // the target. This preserves history but avoids clobbering anything
  // the v2 runtime may have already written.
  const srcDigests = join(legacyDir, "session-digests");
  if (existsSync(srcDigests)) {
    const dstDigests = join(targetDir, "session-digests");
    ensureDir(dstDigests);
    try {
      for (const f of readdirSync(srcDigests)) {
        if (!f.endsWith(".md")) continue;
        const srcFile = join(srcDigests, f);
        const dstFile = join(dstDigests, f);
        if (!existsSync(dstFile)) {
          try { copyFileSync(srcFile, dstFile); migrated++; } catch {}
        }
      }
    } catch {}
  }

  if (migrated > 0) {
    console.log(`         \u2713 Migrated ${migrated} legacy hook state file(s) from ~/.arka-os/`);
    console.log(`         (original files left in place for v1 coexistence)`);
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

  // 3. Update daemon script and core modules
  const daemonSrc = join(arkaosRoot, "bin", "scheduler-daemon.py");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  if (existsSync(daemonSrc)) {
    copyFileSync(daemonSrc, join(binDir, "scheduler-daemon.py"));
    try { chmodSync(join(binDir, "scheduler-daemon.py"), 0o755); } catch {}
    console.log("         \u2713 Scheduler daemon updated");
  }

  // 3b. Update scheduler core modules (daemon imports these at runtime)
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
  console.log("         \u2713 Scheduler core modules updated");

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
      const logDir = join(installDir, "logs");
      const pathValue = `${home}/.local/bin:${home}/.arkaos/bin:/usr/local/bin:/usr/bin:/bin`;
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
