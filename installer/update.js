import { existsSync, readFileSync, writeFileSync, copyFileSync, chmodSync, mkdirSync, readdirSync, cpSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { ensureVenvHealthy, getArkaosPython, pipInstall } from "./python-resolver.js";
import { copyHookLib, copyHookAssets } from "./hook-lib.js";
import { deploySkills } from "./skill-deploy.js";
import { deprecationNotice, resolveSkillsMode } from "./skills-mode.js";
import { deployCoreSnapshot } from "./core-snapshot.js";
import { getRuntimeConfig } from "./detect-runtime.js";
import { loadAdapter } from "./index.js";
import { migrateUserData, printMigrationReport } from "./migrate-user-data.js";
import { resolveFile } from "./path-resolver.js";
import { IS_WINDOWS, HOOK_EXT } from "./platform.js";
import { getUi } from "./ui.js";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ARKAOS_ROOT = resolve(__dirname, "..");
const VERSION = JSON.parse(readFileSync(join(ARKAOS_ROOT, "package.json"), "utf-8")).version;

// UI facade — set at the top of update(). The helpers below delegate to
// it; the plain facade prints the historical byte-identical strings, so
// the auto-update daemon's headless logs remain stable. Update normally
// runs headless (non-TTY), so fancy mode only appears on manual runs.
let ui = null;

function section(n, total, msg) {
  if (ui) return ui.section(n, total, msg);
  console.log(`  [${n}/${total}] ${msg}`);
}

function ok(msg) {
  if (ui) return ui.ok(msg);
  console.log(`         ✓ ${msg}`);
}

function warn(msg) {
  if (ui) return ui.warn(msg);
  console.log(`         ⚠ ${msg}`);
}

function detail(msg) {
  if (ui) return ui.detail(msg);
  console.log(msg);
}

export async function update({ skillsFlag = "" } = {}) {
  ui = await getUi();
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
    warn(`Legacy hook state migration skipped: ${err.message}`);
  }

  // User-data separation (ADR 2026-04-17): move descriptors and ecosystems
  // from ~/.claude/skills/arka/ to ~/.arkaos/. Idempotent, non-destructive.
  try {
    printMigrationReport(migrateUserData());
  } catch (err) {
    warn(`User-data migration skipped: ${err.message}`);
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

  if (ui.isFancy()) {
    ui.intro(`▲ ARKA OS v${VERSION} — Update`);
    ui.clack.log.message(
      `Installed: v${manifest.version}\nPackage:   v${VERSION}\nLatest:    v${latestVersion}`,
    );
  } else {
    console.log(`
  ArkaOS Update
  ─────────────
  Installed: v${manifest.version}
  Package:   v${VERSION}
  Latest:    v${latestVersion}
  `);
  }

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
    if (ui.isFancy()) {
      ui.outro("Already up to date.");
    } else {
      console.log("  ✓ Already up to date.\n");
    }
    return;
  }

  if (isDevCheckout && versionsMatch && !forceRequested) {
    if (ui.isFancy()) {
      ui.clack.log.info("Dev checkout detected — running update even though version matches.");
    } else {
      console.log("  ℹ Dev checkout detected — running update even though version matches.\n");
    }
  }

  if (ui.isFancy()) {
    ui.clack.log.message("Updating (keeping your configuration)...");
  } else {
    console.log("  Updating (keeping your configuration)...\n");
  }

  // ── 1. Update Python deps (using venv) ──
  section(1, 9, "Updating Python dependencies...");

  // Ensure venv is healthy (creates, repairs broken symlinks, or no-ops).
  // PR2 v3.73.1 — previously a stale broken-symlink venv could pass the
  // existence check, and the dashboard would silently fall back to ambient
  // python3 without sqlite-vec/fastembed.
  const venvHealth = ensureVenvHealthy({ log: (msg) => detail(msg) });
  if (!venvHealth.healthy) {
    warn(`Venv unhealthy (${venvHealth.reason}) - falling back to system Python with PEP 668 handling`);
  } else if (venvHealth.repaired) {
    ok(`Venv repaired (${venvHealth.reason})`);
  }

  const pythonCmd = getArkaosPython();
  const log = (msg) => detail(msg);

  // Core deps (always upgrade)
  if (pipInstall("pyyaml pydantic rich click jinja2", { upgrade: true, log })) {
    ok("Core deps updated");
  } else {
    warn("Core deps update failed");
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
      ok("Knowledge deps updated (fastembed, sqlite-vec)");
    } else if (fastembedOk) {
      warn("fastembed upgraded but sqlite-vec failed \u2014 semantic search degraded");
    } else if (sqliteVssOk) {
      warn("sqlite-vec upgraded but fastembed failed \u2014 embedding pipeline degraded");
    } else {
      warn("Knowledge deps upgrade failed \u2014 run: npx arkaos doctor");
    }
  }

  if (pyCheck("fastapi")) {
    if (pipInstall("fastapi uvicorn", { upgrade: true, log, timeout: 60000 })) {
      ok("Dashboard deps updated");
    }
  }

  // Always install ArkaOS core engine
  if (pipInstall("", { editable: ARKAOS_ROOT, log, timeout: 60000 })) {
    ok("ArkaOS core engine installed");
  } else {
    warn("Core engine install failed — run: npx arkaos doctor");
  }

  // ── 2. Update config files ──
  section(2, 9, "Updating configuration...");
  const constitutionSrc = join(ARKAOS_ROOT, "config", "constitution.yaml");
  mkdirSync(join(installDir, "config"), { recursive: true });
  if (existsSync(constitutionSrc)) {
    copyFileSync(constitutionSrc, join(installDir, "config", "constitution.yaml"));
    ok("Constitution updated");
  }
  const statuslineFile = IS_WINDOWS ? "statusline.ps1" : "statusline.sh";
  const statuslineSrc = join(ARKAOS_ROOT, "config", statuslineFile);
  if (existsSync(statuslineSrc)) {
    copyFileSync(statuslineSrc, join(installDir, "config", statuslineFile));
    ok("Statusline updated");
  }
  // Interaction Reform PR1 — refresh the ArkaOS output style file and
  // seed the default (if-absent; explicit operator choice preserved).
  try {
    const { installOutputStyles, seedOutputStyleDefault } = await import("./output-style.js");
    const styleResult = installOutputStyles({
      sourceDir: join(ARKAOS_ROOT, "config", "output-styles"),
    });
    if (styleResult.copied > 0) {
      ok("Output style updated");
    }
    const seedResult = seedOutputStyleDefault({
      runtime: manifest.runtime || "claude-code",
    });
    if (!seedResult.skipped && seedResult.action === "created") {
      ok(`outputStyle default set to "${seedResult.value}"`);
    }
  } catch (err) {
    warn(`Output style update failed (${err.message})`);
  }

  // ── 3. Update hooks ──
  section(3, 9, "Updating hooks...");
  // Keep this list in lockstep with installer/index.js::installHooks and
  // installer/adapters/claude-code.js::hookCommand. Platform-aware: .ps1
  // on Windows, .sh everywhere else.
  const hookNames = [
    "session-start",
    "user-prompt-submit",
    "post-tool-use",
    "pre-compact",
    "cwd-changed",
    "pre-tool-use",
    "stop",
    "subagent-stop",
    "session-end",
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
  ok("Hook scripts updated");

  // Shared hook libraries (config/hooks/_lib/ — the Python interpreter
  // resolver lives here). The hooks deployed above source
  // _lib/arka_python.sh from the install dir, so skipping this copy
  // leaves them falling back to a bare `python3` without ArkaOS deps.
  if (copyHookLib(srcHooksDir, destHooksDir)) {
    ok("Hook lib updated (_lib/)");
  }

  // F2-6 fast-path shims + gate manifest (same shared deploy as the
  // fresh-install path — single asset list in hook-lib.js).
  const assetCount = copyHookAssets(srcHooksDir, destHooksDir);
  if (assetCount > 0) {
    ok(`Hook fast-path assets updated (${assetCount})`);
  }

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
      ok("Hooks re-registered in settings");
    }
  } catch (err) {
    warn(`Could not re-register hooks: ${err.message}`);
  }

  // ── 4. Update CLI wrapper + user CLAUDE.md ──
  section(4, 9, "Updating CLI wrapper and user instructions...");
  const binDir = join(installDir, "bin");
  mkdirSync(binDir, { recursive: true });

  // Platform-aware: bash wrapper on Unix; .ps1 + .cmd shim on Windows.
  if (IS_WINDOWS) {
    const psSrc  = join(ARKAOS_ROOT, "bin", "arka-claude.ps1");
    const cmdSrc = join(ARKAOS_ROOT, "bin", "arka-claude.cmd");
    if (existsSync(psSrc))  copyFileSync(psSrc,  join(binDir, "arka-claude.ps1"));
    if (existsSync(cmdSrc)) copyFileSync(cmdSrc, join(binDir, "arka-claude.cmd"));
    if (existsSync(psSrc) || existsSync(cmdSrc)) {
      ok("arka-claude wrapper updated (.cmd + .ps1)");
    }
    const pyPsSrc  = join(ARKAOS_ROOT, "bin", "arka-py.ps1");
    const pyCmdSrc = join(ARKAOS_ROOT, "bin", "arka-py.cmd");
    if (existsSync(pyPsSrc))  copyFileSync(pyPsSrc,  join(binDir, "arka-py.ps1"));
    if (existsSync(pyCmdSrc)) copyFileSync(pyCmdSrc, join(binDir, "arka-py.cmd"));
    if (existsSync(pyPsSrc) || existsSync(pyCmdSrc)) {
      ok("arka-py interpreter shim updated (.cmd + .ps1)");
    }
  } else {
    const wrapperSrc = join(ARKAOS_ROOT, "bin", "arka-claude");
    if (existsSync(wrapperSrc)) {
      copyFileSync(wrapperSrc, join(binDir, "arka-claude"));
      try { chmodSync(join(binDir, "arka-claude"), 0o755); } catch {}
      ok("arka-claude wrapper updated");
    }
    const arkaPySrc = join(ARKAOS_ROOT, "bin", "arka-py");
    if (existsSync(arkaPySrc)) {
      copyFileSync(arkaPySrc, join(binDir, "arka-py"));
      try { chmodSync(join(binDir, "arka-py"), 0o755); } catch {}
      ok("arka-py interpreter shim updated");
    }
  }
  const userClaudeMd = join(homedir(), ".claude", "CLAUDE.md");
  const claudeMdSrc = join(ARKAOS_ROOT, "config", "user-claude.md");
  if (existsSync(claudeMdSrc)) {
    mkdirSync(join(homedir(), ".claude"), { recursive: true });
    copyFileSync(claudeMdSrc, userClaudeMd);
    ok("~/.claude/CLAUDE.md updated");
  }

  // ── 5. Update Cognitive Scheduler ──
  section(5, 9, "Updating cognitive scheduler...");
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
  section(6, 9, "Updating /arka skill...");
  const skillsBase = join(homedir(), ".claude", "skills");
  const skillDest = join(skillsBase, "arka");
  // Single shared deployment (installer/skill-deploy.js) — identical
  // surface to a fresh install BY CONSTRUCTION: main /arka + nested
  // reference bundle + department hubs + sub-skills + META skills
  // (arka-flow & co. were silently missing from update-only machines
  // before F2-7c-pre) + agent personas.
  const skillsMode = resolveSkillsMode({ flag: skillsFlag, fresh: false });
  if (skillsMode.deprecated) {
    detail("         " + deprecationNotice());
  }
  const skillCounts = deploySkills({
    repoRoot: ARKAOS_ROOT,
    skillsBase,
    agentsBase: join(homedir(), ".claude", "agents"),
    version: VERSION,
    mode: skillsMode.mode,
  });
  ok(`skill set mode: ${skillsMode.mode}`);
  if (skillCounts.main) ok("/arka skill updated");
  if (skillCounts.depts > 0) {
    ok(`${skillCounts.depts} department skills updated`);
  }
  if (skillCounts.subs > 0) {
    ok(`${skillCounts.subs} sub-skills updated`);
  }
  if (skillCounts.meta > 0) {
    ok(`${skillCounts.meta} meta skills updated`);
  }
  if (skillCounts.agents > 0) {
    ok(`${skillCounts.agents} agent personas updated`);
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

    // arka-tools server (F2-3) — mirrors the same block in installSkill().
    const mcpToolsSrc = join(mcpsSrc, "arka-tools");
    const mcpToolsDest = join(skillsBase, "arka", "mcp-tools");
    if (existsSync(mcpToolsSrc)) {
      if (!existsSync(mcpToolsDest)) mkdirSync(mcpToolsDest, { recursive: true });
      for (const f of ["server.py", "pyproject.toml"]) {
        const src = join(mcpToolsSrc, f);
        if (existsSync(src)) copyFileSync(src, join(mcpToolsDest, f));
      }
    }

    ok("MCP infrastructure updated (profiles, stacks, scripts, arka-prompts + arka-tools servers)");

    // Higgsfield MCP is registered but requires an account + API key to connect.
    // Non-blocking warning: the update succeeds even without a Higgsfield account.
    warn("Higgsfield MCP in registry — requires a Higgsfield account + HIGGSFIELD_API_KEY to connect (https://higgsfield.ai). Add per-project: bash apply-mcps.sh --add higgsfield");
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
      ok(`Feature registry: ${featureFiles.length} features copied`);
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
  section(7, 9, "Updating references...");
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  // .repo-path points at the npx cache, which `npm cache clean` can purge;
  // refresh the ~/.arkaos/lib snapshot so arka-py and the Python hooks
  // always keep a validated fallback (see installer/core-snapshot.js).
  // A failed snapshot must never fail the update — resolvers degrade to
  // .repo-path (and any previous snapshot is preserved by the safe swap).
  try {
    if (deployCoreSnapshot(ARKAOS_ROOT, installDir)) {
      ok("Core snapshot refreshed in ~/.arkaos/lib");
    }
  } catch (err) {
    warn(`Core snapshot skipped (${err.message}) — arka-py falls back to .repo-path`);
  }
  const skillsArkaosDir = join(homedir(), ".claude", "skills", "arkaos");
  if (existsSync(skillsArkaosDir)) {
    writeFileSync(join(skillsArkaosDir, ".arkaos-root"), ARKAOS_ROOT);
    ok("Repo path + skills alias updated");
  } else {
    // Fresh install never ran (or user deleted the skills alias);
    // don't recreate it here — that's the install flow's job.
    ok("Repo path updated (skills alias not present)");
  }

  // ── 7b. Frontend UI/UX tooling + Claude plugins ──
  // Mirrors installer/index.js: marketplaces + plugins (ui-ux-pro-max,
  // frontend-design) and Magic MCP + Motion AI Kit. The operator wants
  // these provisioned on update too, not just fresh install. All steps
  // are idempotent and never throw; interactive key prompt is skipped
  // in headless runs.
  const toolingRuntime = manifest.runtime || "claude-code";
  try {
    const { installDefaultClaudePlugins } = await import("./claude-plugins.js");
    const pluginResult = installDefaultClaudePlugins({ runtime: toolingRuntime });
    if (!pluginResult.skipped) {
      for (const m of pluginResult.marketplaces || []) {
        if (m.action === "added") ok(`marketplace ${m.marketplace} added`);
        else if (m.action === "failed") warn(`marketplace ${m.marketplace} failed (${m.reason})`);
      }
      for (const r of pluginResult.results) {
        if (r.action === "installed") ok(`${r.plugin} installed`);
        else if (r.action === "failed") warn(`${r.plugin} failed (${r.reason})`);
      }
    }
  } catch (err) {
    warn(`Could not update Claude plugins (${err.message})`);
  }
  try {
    const { setupFrontendTooling } = await import("./frontend-tooling.js");
    const ft = await setupFrontendTooling({ runtime: toolingRuntime });
    if (ft.magicMcp?.action === "registered") ok("Magic MCP registered (user scope)");
    else if (ft.magicMcp?.action === "already-present") ok("Magic MCP already registered");
    else if (ft.magicMcp?.action === "failed") warn(`Magic MCP failed (${ft.magicMcp.reason})`);
    if (ft.motionKit?.action === "installed") ok("Motion AI Kit installed");
    else if (ft.motionKit?.action === "failed") warn(`Motion AI Kit failed (${ft.motionKit.reason})`);
  } catch (err) {
    warn(`Could not set up frontend tooling (${err.message})`);
  }

  // Graphify grounding layer — same wiring as installer/index.js. Best
  // effort: `npx arkaos update` never fails because of Graphify.
  try {
    const { ensureGraphify, configureGraphifyHttp } = await import("./graphify.js");
    const gf = ensureGraphify();
    if (gf.binary?.installed) {
      ok(`Graphify ready${gf.binary.version ? ` (v${gf.binary.version})` : ""}`);
      if (gf.skillInstall?.action === "installed") {
        ok("Graphify skill registered (graphify install)");
      } else if (gf.skillInstall?.action === "failed") {
        warn(`Graphify skill registration failed (${gf.skillInstall.reason})`);
      }
    } else if (gf.binary?.hint) {
      warn(`${gf.binary.hint}`);
    }
    // Graphify HTTP knowledge-graph MCP (user-scope, config-driven endpoint).
    const gh = await configureGraphifyHttp({ runtime: toolingRuntime });
    if (gh.action === "registered" || gh.action === "re-registered") {
      ok(`Graphify knowledge-graph MCP ${gh.action} (user scope)`);
    } else if (gh.action === "failed") {
      warn(`Graphify knowledge-graph MCP not registered (${gh.reason})`);
    }
  } catch (err) {
    warn(`Could not set up Graphify (${err.message})`);
  }

  // ── 7b. Auto-update daemon (Foundation PR-1) — default-on, opt-out kept ──
  try {
    const { ensureDefaultEnabled } = await import("./autoupdate.js");
    const au = ensureDefaultEnabled({ repoRoot: ARKAOS_ROOT });
    if (au.action === "enabled") ok("Auto-update daemon enabled (daily npm check + notification)");
    else if (au.action === "already-enabled") ok("Auto-update daemon active");
    else if (au.action === "optout") detail("         · Auto-update daemon: user opt-out respected");
  } catch (err) {
    warn(`Auto-update daemon not enabled (${err.message})`);
  }

  // ── 7c. Menu bar launcher (Foundation PR-5) — macOS, default-on ──
  // Opt-out consulted BEFORE pip (QG M3): a disabled menu bar must not
  // cost its dependency on every daemon update. CI runners never get
  // LaunchAgents (QG M4).
  if (process.platform === "darwin" && !process.env.CI) {
    try {
      const { ensureDefaultEnabled: ensureMenubar, status: menubarStatus } =
        await import("./menubar.js");
      if (menubarStatus().optout) {
        detail("         · Menu bar launcher: user opt-out respected");
      } else {
        if (!pipInstall("rumps", { log, timeout: 120000 })) {
          warn("rumps install failed — menu bar app will hint on first run");
        }
        const mb = ensureMenubar({ repoRoot: ARKAOS_ROOT });
        if (mb.action === "enabled") ok("Menu bar launcher enabled (▲ in the macOS menu bar)");
        else if (mb.action === "already-enabled") ok("Menu bar launcher active");
        else if (mb.action === "partial") warn(`Menu bar launcher: ${mb.message}`);
      }
    } catch (err) {
      warn(`Menu bar launcher not enabled (${err.message})`);
    }
  }

  // ── 8. Update manifest ──
  section(8, 9, "Finalizing...");
  manifest.version = VERSION;
  manifest.repoRoot = ARKAOS_ROOT;
  manifest.pythonCmd = pythonCmd;
  manifest.updatedAt = new Date().toISOString();
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  ok("Manifest updated");

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
  ok("Sync state reset (auto-detected on next Claude session)");

  // ── 9. Reconcile profile services (Foundation PR-4) ──
  // Headless by design (the auto-update daemon runs this): only
  // consent-free services install; consent-gated ones (ffmpeg, ollama)
  // report a copy-paste hint. A service failure warns and continues —
  // reconciliation can NEVER block the update.
  section(9, 9, "Reconciling profile services...");
  try {
    const { normalizeProfileFlag } = await import("./profile.js");
    const { reconcileServices } = await import("./services.js");
    const installProfile = normalizeProfileFlag(profile.installProfile) || "essential";
    const results = await reconcileServices({
      profile: installProfile,
      repoRoot: ARKAOS_ROOT,
      interactive: false,
      log: (msg) => detail(msg),
    });
    ok(`profile: ${installProfile}`);
    for (const r of results) {
      if (r.status === "present") ok(`${r.label} present`);
      else if (r.status === "installed") ok(`${r.label} installed`);
      else if (r.status === "skipped") detail(`         · ${r.label} skipped${r.hint ? ` — ${r.hint}` : ""}`);
      else warn(`${r.label} failed${r.hint ? ` — ${r.hint}` : ""}`);
    }
  } catch (err) {
    warn(`Profile service reconciliation skipped (${err.message})`);
  }

  if (ui.isFancy()) {
    ui.stopSpinner();
    const warnCount = ui.warnings().length;
    ui.note(
      [
        `Language:  ${profile.language || "not set"}`,
        `Market:    ${profile.market || "not set"}`,
        `Projects:  ${profile.projectsDir || "not set"}`,
        `Vault:     ${profile.vaultPath || "not set"}`,
        `Profile:   ${profile.installProfile || "essential"}`,
        warnCount > 0 ? `Warnings:  ${warnCount} (see above)` : null,
      ]
        .filter((l) => l !== null)
        .join("\n"),
      `ArkaOS updated to v${VERSION} — configuration preserved`,
    );
    ui.outro("Next Claude Code session auto-detects the update and syncs your projects.");
  } else {
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
}

function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

/**
 * Copy a markdown file, substituting ${VAR} tokens from path-resolver when
 * a profile.json is available. Falls back to plain copy on any error so a
 * missing profile during first install never blocks deployment of the file
 * itself; the agent / Python runtime will resolve later when profile lands.
 */
function safeResolveMarkdown(src, dst) {
  try {
    resolveFile(src, dst);
  } catch {
    copyFileSync(src, dst);
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
    ok(`Migrated ${migrated} legacy hook state file(s) from ~/.arka-os/`);
    detail(`         (original files left in place for v1 coexistence)`);
  }
}

function updateCognitiveScheduler(installDir, arkaosRoot) {
  const platform = process.platform;

  // 1. Update schedule config
  const schedSrc = join(arkaosRoot, "config", "cognition", "schedules.yaml");
  if (existsSync(schedSrc)) {
    copyFileSync(schedSrc, join(installDir, "schedules.yaml"));
    ok("Schedule config updated");
  }

  // 2. Update prompt files
  const promptsDir = join(installDir, "cognition", "prompts");
  ensureDir(promptsDir);
  const promptsSrc = join(arkaosRoot, "config", "cognition", "prompts");
  if (existsSync(promptsSrc)) {
    for (const f of readdirSync(promptsSrc)) {
      const src = join(promptsSrc, f);
      const dst = join(promptsDir, f);
      if (f.endsWith(".md")) {
        safeResolveMarkdown(src, dst);
      } else {
        copyFileSync(src, dst);
      }
    }
    ok("Cognitive prompts updated");
  }

  // 3. Update daemon script and core modules
  const daemonSrc = join(arkaosRoot, "bin", "scheduler-daemon.py");
  const binDir = join(installDir, "bin");
  ensureDir(binDir);
  if (existsSync(daemonSrc)) {
    copyFileSync(daemonSrc, join(binDir, "scheduler-daemon.py"));
    try { chmodSync(join(binDir, "scheduler-daemon.py"), 0o755); } catch {}
    ok("Scheduler daemon updated");
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
  ok("Scheduler core modules updated");

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
        ok("Scheduler service restarted (launchd)");
      } catch {
        warn("Scheduler reload failed — restart manually");
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
        ok("Scheduler service installed and started (launchd)");
      } catch {
        warn("Scheduler plist written but load failed");
      }
    }
  } else if (platform === "linux") {
    try {
      execSync("systemctl --user restart arkaos-scheduler.service 2>/dev/null", { stdio: "pipe" });
      ok("Scheduler service restarted (systemd)");
    } catch {
      warn("Scheduler not running — install with: npx arkaos install");
    }
  }
}
