/**
 * Cross-OS package manager abstraction for the ArkaOS installer.
 *
 * Centralises detection of brew (macOS), winget/choco (Windows) and
 * apt/snap (Linux) so install/update flows can either run a non-sudo
 * install themselves or return a copy-paste command for the user.
 *
 * **Never invokes sudo automatically.** When sudo is required (apt /
 * snap on Linux, winget without elevation), `installViaPackageManager`
 * returns `{ needsSudo: true, command }` and the caller is expected
 * to print the command for the user to run. This keeps the installer
 * headless-safe — it must not surprise a CI job with a password prompt.
 *
 * See core/specs/SPEC-installer-cross-os.md (PR2 v2.24.0).
 */

import { execSync } from "node:child_process";
import { platform } from "node:os";
import { IS_WINDOWS } from "./platform.js";

const MAC = "darwin";
const LINUX = "linux";

/**
 * Detect the highest-priority package manager available on this host.
 *
 * Priority order:
 *   macOS:   brew
 *   Linux:   apt > snap (apt for generic packages; snap preferred for
 *            Obsidian because its tarball is classic-confined)
 *   Windows: winget > choco
 *
 * Returns the canonical name string or null when nothing is available.
 */
export function detectPackageManager() {
  const candidates = preferredCandidates();
  for (const name of candidates) {
    if (hasCommand(name)) return name;
  }
  return null;
}

/**
 * Return every package manager available on this host, in priority order.
 * Useful for callers that need a different manager per package (e.g.
 * snap for Obsidian on a host that also has apt for Node).
 */
export function detectAllPackageManagers() {
  return preferredCandidates().filter((name) => hasCommand(name));
}

/**
 * Build the install command for a package on a given manager, without
 * executing it. Useful for `formatSudoInstructions` and for dry-run paths.
 */
export function buildInstallCommand(manager, pkg) {
  switch (manager) {
    case "brew":
      return pkg.startsWith("cask:")
        ? `brew install --cask ${pkg.slice(5)}`
        : `brew install ${pkg}`;
    case "apt":
      return `sudo apt update && sudo apt install -y ${pkg}`;
    case "snap":
      return pkg.endsWith(":classic")
        ? `sudo snap install ${pkg.slice(0, -8)} --classic`
        : `sudo snap install ${pkg}`;
    case "winget":
      return `winget install --id ${pkg} --silent --accept-source-agreements --accept-package-agreements`;
    case "choco":
      return `choco install ${pkg} -y`;
    default:
      return "";
  }
}

/**
 * Whether a manager needs sudo (or Windows elevation) for install.
 * brew on macOS is intentionally not sudo-gated (Homebrew runs as the user).
 */
export function managerNeedsSudo(manager) {
  return manager === "apt" || manager === "snap";
}

/**
 * Attempt a non-sudo install. When the chosen manager requires sudo
 * we never invoke it ourselves — the caller surfaces the command to
 * the user. Returns a structured result the caller can react to.
 */
export function installViaPackageManager(pkg, options = {}) {
  const manager = options.manager || detectPackageManager();
  if (!manager) {
    return {
      success: false,
      manager: null,
      command: "",
      needsSudo: false,
      installed: false,
      error: "no_package_manager",
      fallbackUrl: options.fallbackUrl || null,
    };
  }

  const command = buildInstallCommand(manager, pkg);
  const needsSudo = managerNeedsSudo(manager);

  if (needsSudo) {
    return {
      success: true,
      manager,
      command,
      needsSudo: true,
      installed: false,
      error: null,
    };
  }

  if (options.dryRun) {
    return {
      success: true,
      manager,
      command,
      needsSudo: false,
      installed: false,
      error: null,
    };
  }

  try {
    execSync(command, { stdio: "inherit" });
    return {
      success: true,
      manager,
      command,
      needsSudo: false,
      installed: true,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      manager,
      command,
      needsSudo: false,
      installed: false,
      error: err?.message || "install_failed",
    };
  }
}

/**
 * Format an array of sudo install commands into a copy-paste block.
 * Used by ensureSystemTools to print a single, friendly block when
 * several packages need privileged install on Linux.
 */
export function formatSudoInstructions(commands) {
  if (!commands || commands.length === 0) return "";
  const unique = [...new Set(commands.filter(Boolean))];
  if (unique.length === 0) return "";
  const lines = [
    "",
    "  To finish setup, please run these commands:",
    "",
    ...unique.map((c) => `    ${c}`),
    "",
    "  Then re-run: npx arkaos install",
    "",
  ];
  return lines.join("\n");
}

function preferredCandidates() {
  const os = platform();
  if (os === MAC) return ["brew"];
  if (os === LINUX) return ["apt", "snap"];
  if (IS_WINDOWS) return ["winget", "choco"];
  return [];
}

function hasCommand(name) {
  const finder = IS_WINDOWS ? "where" : "command -v";
  try {
    execSync(`${finder} ${name}`, {
      stdio: ["ignore", "ignore", "ignore"],
      shell: !IS_WINDOWS,
    });
    return true;
  } catch {
    return false;
  }
}
