/**
 * ArkaOS Python Resolver — single source of truth for Python interpreter.
 *
 * Strategy: always use ~/.arkaos/venv. This isolates ArkaOS from system
 * Python, avoids PEP 668 issues on macOS/Homebrew and Ubuntu 23.04+,
 * and guarantees the doctor checks the same interpreter the installer uses.
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir, platform } from "node:os";
import { execSync } from "node:child_process";

const INSTALL_DIR = join(homedir(), ".arkaos");

/**
 * Return the path to the venv's Python interpreter.
 * On Windows: ~/.arkaos/venv/Scripts/python.exe
 * On Unix:    ~/.arkaos/venv/bin/python
 */
export function getVenvPython() {
  if (platform() === "win32") {
    return join(INSTALL_DIR, "venv", "Scripts", "python.exe");
  }
  return join(INSTALL_DIR, "venv", "bin", "python");
}

/**
 * Return the path to the venv's pip.
 */
export function getVenvPip() {
  if (platform() === "win32") {
    return join(INSTALL_DIR, "venv", "Scripts", "pip.exe");
  }
  return join(INSTALL_DIR, "venv", "bin", "pip");
}

/**
 * Return the ArkaOS Python interpreter — venv if it exists, fallback to system.
 * This is the ONLY function other modules should use to get a Python path.
 */
export function getArkaosPython() {
  const venvPy = getVenvPython();
  if (existsSync(venvPy)) {
    return venvPy;
  }
  // Fallback to system Python (for pre-venv installations)
  return findSystemPython();
}

/**
 * Return the ArkaOS pip — venv if it exists, fallback to system.
 */
export function getArkaosPip() {
  const venvPip = getVenvPip();
  if (existsSync(venvPip)) {
    return venvPip;
  }
  // Fallback: use python -m pip with PEP 668 handling
  return null;
}

/**
 * Find system Python 3.11+ (used only during initial venv creation).
 */
export function findSystemPython() {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, { stdio: "pipe" }).toString().trim();
      const match = version.match(/(\d+)\.(\d+)/);
      if (match && parseInt(match[1]) >= 3 && parseInt(match[2]) >= 11) {
        // Resolve to absolute path
        try {
          const resolved = execSync(`which ${cmd} 2>/dev/null || where ${cmd} 2>nul`, { stdio: "pipe" })
            .toString().trim().split("\n")[0];
          return resolved || cmd;
        } catch {
          return cmd;
        }
      }
    } catch {
      continue;
    }
  }
  return null;
}

/**
 * Create the ArkaOS venv if it doesn't exist.
 * Returns true on success, false on failure.
 */
export function ensureVenv(log = console.log) {
  const venvDir = join(INSTALL_DIR, "venv");
  const venvPy = getVenvPython();

  if (existsSync(venvPy)) {
    return true; // Already exists
  }

  const systemPython = findSystemPython();
  if (!systemPython) {
    log("         \u26a0 No Python 3.11+ found — cannot create venv");
    return false;
  }

  try {
    execSync(`"${systemPython}" -m venv "${venvDir}"`, { stdio: "pipe", timeout: 60000 });
    log(`         \u2713 Virtual environment created at ${venvDir}`);

    // Upgrade pip inside the venv
    try {
      execSync(`"${venvPy}" -m pip install --upgrade pip --quiet`, { stdio: "pipe", timeout: 60000 });
    } catch { /* pip upgrade is non-critical */ }

    return true;
  } catch (err) {
    log(`         \u26a0 Failed to create venv: ${err.message.slice(0, 100)}`);
    return false;
  }
}

/**
 * Install Python packages using the ArkaOS interpreter.
 * Uses venv pip (no PEP 668 issues) or falls back with --break-system-packages.
 */
export function pipInstall(packages, opts = {}) {
  const { quiet = true, upgrade = false, editable = null, timeout = 120000, log = console.log } = opts;

  const venvPip = getArkaosPip();
  const arkaosPy = getArkaosPython();

  const flags = [];
  if (quiet) flags.push("--quiet");
  if (upgrade) flags.push("--upgrade");

  const pkgArg = editable ? `-e "${editable}"` : packages;

  // Strategy 1: Use venv pip directly (preferred — no PEP 668)
  if (venvPip && existsSync(venvPip)) {
    try {
      execSync(`"${venvPip}" install ${flags.join(" ")} ${pkgArg}`, { stdio: "pipe", timeout });
      return true;
    } catch (err) {
      log(`         \u26a0 Venv pip install failed: ${err.message.slice(0, 80)}`);
      return false;
    }
  }

  // Strategy 2: Use python -m pip (system Python — handle PEP 668)
  if (arkaosPy) {
    // Try without --break-system-packages first
    try {
      execSync(`"${arkaosPy}" -m pip install ${flags.join(" ")} ${pkgArg}`, { stdio: "pipe", timeout });
      return true;
    } catch (err) {
      const stderr = err.stderr ? err.stderr.toString() : err.message;
      if (stderr.includes("externally-managed-environment")) {
        // PEP 668 — retry with --break-system-packages
        log("         \u26a0 PEP 668 detected — retrying with --break-system-packages");
        try {
          execSync(`"${arkaosPy}" -m pip install --break-system-packages ${flags.join(" ")} ${pkgArg}`, {
            stdio: "pipe", timeout,
          });
          return true;
        } catch (err2) {
          log(`         \u26a0 pip install with --break-system-packages also failed: ${err2.message.slice(0, 80)}`);
          return false;
        }
      }
      log(`         \u26a0 pip install failed: ${err.message.slice(0, 80)}`);
      return false;
    }
  }

  log("         \u26a0 No Python interpreter available for pip install");
  return false;
}

/**
 * Check if the ArkaOS Python can import the core engine.
 */
export function canImportCore() {
  const py = getArkaosPython();
  if (!py || !existsSync(py)) return false;
  try {
    execSync(`"${py}" -c "from core.synapse.engine import SynapseEngine"`, {
      stdio: "pipe",
      timeout: 10000,
      cwd: getRepoRoot(),
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get the ArkaOS repo root from .repo-path or manifest.
 */
export function getRepoRoot() {
  const repoPathFile = join(INSTALL_DIR, ".repo-path");
  if (existsSync(repoPathFile)) {
    const p = execSync(`cat "${repoPathFile}"`, { stdio: "pipe" }).toString().trim();
    if (existsSync(p)) return p;
  }
  // Fallback: try manifest
  const manifestPath = join(INSTALL_DIR, "install-manifest.json");
  if (existsSync(manifestPath)) {
    try {
      const m = JSON.parse(execSync(`cat "${manifestPath}"`, { stdio: "pipe" }).toString());
      if (m.repoRoot && existsSync(m.repoRoot)) return m.repoRoot;
    } catch {}
  }
  return null;
}
