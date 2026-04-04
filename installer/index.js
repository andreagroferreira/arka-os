import { existsSync, mkdirSync, copyFileSync, readFileSync, writeFileSync } from "node:fs";
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

  // Step 1: Create installation directory
  console.log("  [1/7] Creating directories...");
  ensureDir(installDir);
  ensureDir(join(installDir, "config"));
  ensureDir(join(installDir, "agents"));
  ensureDir(join(installDir, "media"));
  ensureDir(join(installDir, "session-digests"));

  // Step 2: Check Python availability
  console.log("  [2/7] Checking Python...");
  const pythonCmd = checkPython();
  console.log(`         Found: ${pythonCmd}`);

  // Step 3: Install Python dependencies
  console.log("  [3/7] Installing Python core engine...");
  installPythonDeps(pythonCmd);

  // Step 4: Copy skills to runtime
  console.log("  [4/7] Installing skills & agents...");
  const skillsDir = join(config.skillsDir, "arkaos");
  installSkills(skillsDir, force);

  // Step 5: Configure runtime hooks
  console.log("  [5/7] Configuring runtime hooks...");
  const adapter = await loadAdapter(runtime);
  adapter.configureHooks(config, installDir);

  // Step 6: Create user profile (if first install)
  console.log("  [6/7] Checking user profile...");
  const profilePath = join(installDir, "profile.json");
  if (!existsSync(profilePath)) {
    console.log("         New installation — profile will be created on first run.");
    writeFileSync(
      profilePath,
      JSON.stringify({ version: "2", created: new Date().toISOString() }, null, 2)
    );
  } else {
    console.log("         Profile exists, preserving.");
  }

  // Step 7: Write install manifest
  console.log("  [7/7] Finalizing...");
  const manifest = {
    version: VERSION,
    runtime,
    installDir,
    configDir: config.configDir,
    skillsDir: skillsDir,
    installedAt: new Date().toISOString(),
    pythonCmd,
  };
  writeFileSync(join(installDir, "install-manifest.json"), JSON.stringify(manifest, null, 2));

  console.log(`
  ArkaOS v${VERSION} installed successfully!

  Runtime:     ${config.name}
  Install dir: ${installDir}
  Skills dir:  ${skillsDir}

  Get started:
    Type any request in ${config.name} and ArkaOS will route it.
    Use /do <description> for natural language commands.
    Use arkaos doctor to verify installation.
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
    // Try uv first (faster), fall back to pip
    try {
      execSync("uv --version", { stdio: "pipe" });
      execSync(`uv pip install -e "${ARKAOS_ROOT}"`, { stdio: "pipe" });
      return;
    } catch {
      // uv not available, use pip
    }
    execSync(`${pythonCmd} -m pip install -e "${ARKAOS_ROOT}" --quiet`, { stdio: "pipe" });
  } catch (err) {
    console.warn("         Warning: Could not install Python deps. Core engine may not work.");
    console.warn(`         ${err.message}`);
  }
}

function installSkills(skillsDir, force) {
  ensureDir(skillsDir);
  // Skills are loaded from the package at runtime, not copied
  // We just create a symlink or reference file
  const refFile = join(skillsDir, ".arkaos-root");
  writeFileSync(refFile, ARKAOS_ROOT);
}

async function loadAdapter(runtime) {
  try {
    const mod = await import(`./adapters/${runtime}.js`);
    return mod.default;
  } catch {
    // Fallback to generic adapter
    return {
      configureHooks(config, installDir) {
        console.log(`         Using generic configuration for ${runtime}`);
      },
    };
  }
}
