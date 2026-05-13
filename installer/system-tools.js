/**
 * Cross-OS system-tool guarantor for the ArkaOS installer.
 *
 * Validates that the three external dependencies ArkaOS needs at runtime
 * — Obsidian, Node.js ≥ 20, Python ≥ 3.12 — are present. Tools that can
 * be installed without sudo (brew on macOS, winget on Windows) are
 * installed automatically. Tools that need sudo (apt/snap on Linux) get
 * a copy-paste command surfaced via `sudoCommands`.
 *
 * Idempotent: tools already at an acceptable version are no-ops.
 *
 * Spec: core/specs/SPEC-installer-cross-os.md (PR2 v2.24.0).
 */

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { platform } from "node:os";
import { IS_WINDOWS, CMD_FINDER } from "./platform.js";
import {
  buildInstallCommand,
  detectAllPackageManagers,
  detectPackageManager,
  installViaPackageManager,
  managerNeedsSudo,
} from "./package-manager.js";

const NODE_MIN_MAJOR = 20;
const PYTHON_MIN = { major: 3, minor: 12 };

const OBSIDIAN_PACKAGE = {
  brew: "cask:obsidian",
  snap: "obsidian:classic",
  winget: "Obsidian.Obsidian",
  choco: "obsidian",
};

const NODE_PACKAGE = {
  brew: "node",
  apt: "nodejs",
  winget: "OpenJS.NodeJS",
  choco: "nodejs",
};

const OLLAMA_PACKAGE = {
  brew: "ollama",
  winget: "Ollama.Ollama",
  choco: "ollama",
};

const OBSIDIAN_FALLBACK_URL = "https://obsidian.md/download";
const NODE_FALLBACK_URL = "https://nodejs.org/en/download";
const PYTHON_FALLBACK_URL = "https://www.python.org/downloads/";
const OLLAMA_FALLBACK_URL = "https://ollama.com/download";

/**
 * Validate every required tool, install what can be installed without
 * sudo, and collect copy-paste commands for the ones that can't.
 *
 * When ``options.withCognitive`` is set, Ollama (cognitive-layer LLM
 * runtime) is included in the check + install set. Opt-in so existing
 * 20K-user installs are not surprised by a 4GB+ Ollama download.
 */
export function ensureSystemTools(options = {}) {
  if (options.skipSystem) {
    return {
      skipped: true,
      obsidian: null,
      node: null,
      python: null,
      ollama: null,
      sudoCommands: [],
    };
  }

  const obsidian = ensureTool("obsidian", checkObsidian, OBSIDIAN_PACKAGE, OBSIDIAN_FALLBACK_URL, options);
  const node = ensureTool("node", checkNode, NODE_PACKAGE, NODE_FALLBACK_URL, options);
  const python = checkPython();  // never auto-install Python — leave to OS

  let ollama = null;
  if (options.withCognitive) {
    ollama = ensureTool("ollama", checkOllama, OLLAMA_PACKAGE, OLLAMA_FALLBACK_URL, options);
  }

  const tools = [obsidian, node, ollama].filter(Boolean);
  const sudoCommands = tools
    .filter((t) => t?.needsSudo && t.suggestedCommand)
    .map((t) => t.suggestedCommand);

  if (python.needsAction !== "none" && python.suggestedCommand) {
    sudoCommands.push(python.suggestedCommand);
  }

  return { skipped: false, obsidian, node, python, ollama, sudoCommands };
}

/**
 * Cheap presence + version check for Obsidian. Looks for the binary
 * via OS-native finder and falls back to known install paths.
 */
export function checkObsidian() {
  const location = findBinary("obsidian") || findObsidianAppPath();
  if (location) {
    return {
      name: "obsidian",
      installed: true,
      location,
      needsAction: "none",
    };
  }
  const suggested = buildSuggestedInstall(OBSIDIAN_PACKAGE, OBSIDIAN_FALLBACK_URL);
  return {
    name: "obsidian",
    installed: false,
    needsAction: "install",
    suggestedCommand: suggested.command,
    needsSudo: suggested.needsSudo,
    fallbackUrl: suggested.fallbackUrl,
  };
}

export function checkNode() {
  const location = findBinary("node");
  if (!location) {
    const suggested = buildSuggestedInstall(NODE_PACKAGE, NODE_FALLBACK_URL);
    return {
      name: "node",
      installed: false,
      needsAction: "install",
      suggestedCommand: suggested.command,
      needsSudo: suggested.needsSudo,
      fallbackUrl: suggested.fallbackUrl,
    };
  }
  const version = readNodeVersion();
  const major = version ? Number(version.split(".")[0]) : 0;
  if (major >= NODE_MIN_MAJOR) {
    return { name: "node", installed: true, location, version, needsAction: "none" };
  }
  const suggested = buildSuggestedInstall(NODE_PACKAGE, NODE_FALLBACK_URL);
  return {
    name: "node",
    installed: true,
    location,
    version,
    needsAction: "upgrade",
    suggestedCommand: suggested.command,
    needsSudo: suggested.needsSudo,
    fallbackUrl: suggested.fallbackUrl,
  };
}

/**
 * Detect Ollama presence + whether the local service responds.
 *
 * Ollama is the cognitive-layer LLM runtime. Linux install uses an
 * official script (``curl https://ollama.com/install.sh | sh``) that
 * requires sudo — we never run it; we surface the command.
 */
export function checkOllama() {
  const location = findBinary("ollama");
  if (!location) {
    const suggested = buildOllamaSuggestion();
    return {
      name: "ollama",
      installed: false,
      needsAction: "install",
      suggestedCommand: suggested.command,
      needsSudo: suggested.needsSudo,
      fallbackUrl: OLLAMA_FALLBACK_URL,
    };
  }
  const reachable = isOllamaReachable();
  const version = readVersion("ollama --version");
  return {
    name: "ollama",
    installed: true,
    location,
    version,
    needsAction: reachable ? "none" : "start",
    suggestedCommand: reachable ? undefined : "ollama serve   # or run the Ollama app",
    needsSudo: false,
  };
}


export function checkPython() {
  const candidates = IS_WINDOWS ? ["python", "py"] : ["python3", "python3.12", "python3.13"];
  for (const cmd of candidates) {
    const location = findBinary(cmd);
    if (!location) continue;
    const version = readVersion(`${cmd} --version`);
    const ok = versionAtLeast(version, PYTHON_MIN.major, PYTHON_MIN.minor);
    if (ok) {
      return { name: "python", installed: true, location, version, needsAction: "none" };
    }
  }
  return {
    name: "python",
    installed: false,
    needsAction: "install",
    suggestedCommand: `Install Python ${PYTHON_MIN.major}.${PYTHON_MIN.minor}+ from ${PYTHON_FALLBACK_URL}`,
    needsSudo: false,
    fallbackUrl: PYTHON_FALLBACK_URL,
  };
}

function ensureTool(name, checkFn, packageMap, fallbackUrl, options) {
  const status = checkFn();
  if (status.needsAction === "none") return status;

  const manager = detectPackageManager();
  if (!manager || !packageMap[manager]) {
    return { ...status, fallbackUrl };
  }

  if (managerNeedsSudo(manager)) {
    return {
      ...status,
      suggestedCommand: buildInstallCommand(manager, packageMap[manager]),
      needsSudo: true,
    };
  }

  if (options.dryRun) return status;

  const result = installViaPackageManager(packageMap[manager], {
    manager,
    fallbackUrl,
  });
  if (result.installed) {
    return { ...checkFn(), justInstalled: true };
  }
  return { ...status, error: result.error };
}

function buildSuggestedInstall(packageMap, fallbackUrl) {
  const managers = detectAllPackageManagers();
  for (const m of managers) {
    if (packageMap[m]) {
      return {
        command: buildInstallCommand(m, packageMap[m]),
        needsSudo: managerNeedsSudo(m),
        fallbackUrl,
      };
    }
  }
  return { command: `Download from ${fallbackUrl}`, needsSudo: false, fallbackUrl };
}

function buildOllamaSuggestion() {
  const os = platform();
  if (os === "darwin") return { command: "brew install ollama", needsSudo: false };
  if (IS_WINDOWS) return { command: "winget install --id Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements", needsSudo: false };
  if (os === "linux") return { command: "curl -fsSL https://ollama.com/install.sh | sh", needsSudo: true };
  return { command: `Download from ${OLLAMA_FALLBACK_URL}`, needsSudo: false };
}


function isOllamaReachable() {
  try {
    execSync("ollama list", {
      stdio: ["ignore", "ignore", "ignore"],
      timeout: 1500,
    });
    return true;
  } catch {
    return false;
  }
}


function findBinary(name) {
  try {
    const out = execSync(`${CMD_FINDER} ${name}`, {
      stdio: ["ignore", "pipe", "ignore"],
    }).toString().trim().split(/\r?\n/)[0];
    return out || null;
  } catch {
    return null;
  }
}

function findObsidianAppPath() {
  if (platform() === "darwin") {
    const mac = "/Applications/Obsidian.app";
    if (existsSync(mac)) return mac;
  }
  if (IS_WINDOWS) {
    const localApp = process.env.LOCALAPPDATA;
    if (localApp) {
      const candidate = `${localApp}\\Obsidian\\Obsidian.exe`;
      if (existsSync(candidate)) return candidate;
    }
  }
  return null;
}

function readNodeVersion() {
  return readVersion("node --version");
}

function readVersion(command) {
  try {
    const out = execSync(command, { stdio: ["ignore", "pipe", "ignore"] }).toString();
    const match = out.match(/(\d+\.\d+(?:\.\d+)?)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function versionAtLeast(version, major, minor) {
  if (!version) return false;
  const parts = version.split(".").map((n) => Number(n) || 0);
  if (parts[0] !== major) return parts[0] > major;
  return parts[1] >= minor;
}
