import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync, readdirSync, chmodSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { getRuntimeConfig } from "./detect-runtime.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ARKAOS_ROOT = resolve(__dirname, "..");

const VERSION = "2.0.0-alpha.1";

export async function install({ runtime, path, force }) {
  console.log(`\n  ArkaOS v${VERSION} — The Operating System for AI Agent Teams\n`);
  console.log(`  Runtime: ${runtime}`);

  const config = getRuntimeConfig(runtime);
  const installDir = path || join(homedir(), ".arkaos");

  console.log(`  Install dir: ${installDir}`);
  console.log(`  Config dir: ${config.configDir}\n`);

  // Step 1: Create directories
  console.log("  [1/8] Creating directories...");
  ensureDir(installDir);
  ensureDir(join(installDir, "config"));
  ensureDir(join(installDir, "config", "hooks"));
  ensureDir(join(installDir, "agents"));
  ensureDir(join(installDir, "media"));
  ensureDir(join(installDir, "session-digests"));

  // Step 2: Check Python
  console.log("  [2/8] Checking Python...");
  const pythonCmd = checkPython();
  console.log(`         Found: ${pythonCmd}`);

  // Step 3: Install Python core engine
  console.log("  [3/8] Installing Python core engine...");
  installPythonDeps(pythonCmd);

  // Step 4: Copy config files
  console.log("  [4/8] Copying configuration files...");
  copyConfigFiles(installDir);

  // Step 5: Install hooks
  console.log("  [5/8] Installing hooks...");
  installHooks(installDir);

  // Step 6: Configure runtime
  console.log("  [6/8] Configuring runtime...");
  const adapter = await loadAdapter(runtime);
  adapter.configureHooks(config, installDir);

  // Step 7: Create references
  console.log("  [7/8] Creating references...");
  // .repo-path: so hooks can find the package
  writeFileSync(join(installDir, ".repo-path"), ARKAOS_ROOT);
  // Skills reference
  const skillsDir = join(config.skillsDir, "arkaos");
  ensureDir(skillsDir);
  writeFileSync(join(skillsDir, ".arkaos-root"), ARKAOS_ROOT);
  // Profile (first install only)
  const profilePath = join(installDir, "profile.json");
  if (!existsSync(profilePath)) {
    console.log("         New installation — profile created.");
    writeFileSync(profilePath, JSON.stringify({
      version: "2",
      created: new Date().toISOString(),
    }, null, 2));
  }

  // Step 8: Finalize
  console.log("  [8/8] Finalizing...");
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

  console.log(`
  ArkaOS v${VERSION} installed successfully!

  Runtime:     ${config.name}
  Install dir: ${installDir}
  Repo root:   ${ARKAOS_ROOT}

  Get started:
    Type any request in ${config.name} and ArkaOS will route it.
    Use /do <description> for natural language commands.
    Run: npx arkaos doctor    to verify installation.
  `);
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
  console.error(
    "\n  Python 3.11+ is required but not found.\n" +
      "  Install Python: https://python.org/downloads/\n"
  );
  process.exit(1);
}

function installPythonDeps(pythonCmd) {
  try {
    try {
      execSync("uv --version", { stdio: "pipe" });
      execSync(`uv pip install -e "${ARKAOS_ROOT}"`, { stdio: "pipe" });
      return;
    } catch {
      // uv not available
    }
    execSync(`${pythonCmd} -m pip install -e "${ARKAOS_ROOT}" --quiet`, { stdio: "pipe" });
  } catch (err) {
    console.warn("         Warning: Could not install Python deps. Core engine may not work.");
    console.warn(`         ${err.message}`);
  }
}

function copyConfigFiles(installDir) {
  // Constitution
  const constitutionSrc = join(ARKAOS_ROOT, "config", "constitution.yaml");
  if (existsSync(constitutionSrc)) {
    copyFileSync(constitutionSrc, join(installDir, "config", "constitution.yaml"));
  }
}

function installHooks(installDir) {
  const hooksDir = join(installDir, "config", "hooks");
  ensureDir(hooksDir);

  // Copy v2 hooks, rename to standard names (without -v2 suffix)
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
      // Read, replace ARKAOS_ROOT placeholder, write
      let content = readFileSync(srcPath, "utf-8");
      // Ensure hooks use the install directory
      content = content.replace(
        /ARKAOS_ROOT="\$\{ARKA_OS:-\$HOME\/\.claude\/skills\/arkaos\}"/g,
        `ARKAOS_ROOT="${installDir}"`
      );
      content = content.replace(
        /ARKAOS_HOME="\$\{HOME\}\/\.arkaos"/g,
        `ARKAOS_HOME="${installDir}"`
      );
      writeFileSync(destPath, content);
      try {
        chmodSync(destPath, 0o755);
      } catch { /* ignore on Windows */ }
      console.log(`         Installed: ${dest}`);
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
