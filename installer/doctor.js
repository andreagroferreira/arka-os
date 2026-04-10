import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { getArkaosPython, getVenvPython, canImportCore, getRepoRoot } from "./python-resolver.js";
import { IS_WINDOWS, HOOK_EXT, CMD_FINDER } from "./platform.js";

const INSTALL_DIR = join(homedir(), ".arkaos");

// Resolve a single command via the platform-native locator. Returns true
// when the command is discoverable on PATH, false otherwise. stderr is
// suppressed through Node's stdio option so the probe does not print
// noise when the command is missing.
function commandExists(cmd) {
  const finder = CMD_FINDER;
  try {
    execSync(`${finder} ${cmd}`, { stdio: ["pipe", "pipe", "ignore"] });
    return true;
  } catch {
    return false;
  }
}

const checks = [
  {
    name: "install-dir",
    description: "ArkaOS installation directory exists",
    severity: "fail",
    check: () => existsSync(INSTALL_DIR),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "manifest",
    description: "Install manifest present",
    severity: "fail",
    check: () => existsSync(join(INSTALL_DIR, "install-manifest.json")),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "python",
    description: "Python 3.11+ available",
    severity: "fail",
    check: () => {
      const py = getArkaosPython();
      if (!py) return false;
      try {
        const v = execSync(`"${py}" --version 2>&1`, { stdio: "pipe" }).toString();
        const m = v.match(/(\d+)\.(\d+)/);
        return m && parseInt(m[1]) >= 3 && parseInt(m[2]) >= 11;
      } catch { return false; }
    },
    fix: () => "Install Python 3.11+: https://python.org",
  },
  {
    name: "venv",
    description: "ArkaOS virtual environment exists",
    severity: "warn",
    check: () => existsSync(getVenvPython()),
    fix: () => "Run: npx arkaos@latest update (creates venv automatically)",
  },
  {
    name: "hooks-dir",
    description: "Hook scripts installed",
    severity: "fail",
    check: () => existsSync(join(INSTALL_DIR, "config", "hooks", `user-prompt-submit${HOOK_EXT}`)),
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "constitution",
    description: "Constitution YAML present",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "config", "constitution.yaml")),
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "repo-path",
    description: "Repo path reference exists",
    severity: "warn",
    check: () => {
      const p = join(INSTALL_DIR, ".repo-path");
      if (!existsSync(p)) return false;
      const root = readFileSync(p, "utf-8").trim();
      return existsSync(root);
    },
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "profile",
    description: "User profile exists",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "profile.json")),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "python-core",
    description: "Python core engine importable",
    severity: "warn",
    check: () => canImportCore(),
    fix: () => {
      const py = getArkaosPython();
      const root = getRepoRoot();
      if (py && root) {
        return `Run: "${py}" -m pip install -e "${root}"`;
      }
      return "Run: npx arkaos@latest update (reinstalls Python core)";
    },
  },
  {
    name: "scheduler",
    description: "Cognitive scheduler config deployed",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "schedules.yaml")),
    fix: () => "Run: npx arkaos@latest update (deploys scheduler)",
  },
];

// ─── Windows-only checks ───────────────────────────────────────────────
// Appended conditionally so non-Windows runs are byte-for-byte unchanged.
if (IS_WINDOWS) {
  checks.push(
    {
      name: "powershell",
      description: "PowerShell 5.1+ available",
      severity: "fail",
      check: () => {
        try {
          const out = execSync(
            'powershell -NoProfile -Command "$PSVersionTable.PSVersion.Major"',
            { stdio: ["pipe", "pipe", "ignore"] }
          ).toString().trim();
          const major = parseInt(out, 10);
          return Number.isFinite(major) && major >= 5;
        } catch {
          return false;
        }
      },
      fix: () => "Install Windows PowerShell 5.1+ (ships with every Windows 10/11).",
    },
    {
      name: "arka-claude-wrapper",
      description: "arka-claude wrapper installed (.cmd + .ps1)",
      severity: "warn",
      check: () =>
        existsSync(join(INSTALL_DIR, "bin", "arka-claude.cmd")) &&
        existsSync(join(INSTALL_DIR, "bin", "arka-claude.ps1")),
      fix: () => "Run: npx arkaos install --force",
    },
    {
      name: "schtasks",
      description: "schtasks available (cognitive scheduler backend)",
      severity: "warn",
      check: () => commandExists("schtasks"),
      fix: () => "schtasks ships with Windows by default; verify %WINDIR%\\System32 is on PATH.",
    },
    {
      name: "venv-scripts",
      description: "Venv Python at %USERPROFILE%\\.arkaos\\venv\\Scripts\\python.exe",
      severity: "warn",
      check: () => {
        const venvPy = getVenvPython();
        // Only meaningful if venv exists at all. The "venv" check above
        // covers absence; this one guards against a macOS-shaped venv
        // being mistaken for a Windows venv (bin/ instead of Scripts/).
        if (!existsSync(join(INSTALL_DIR, "venv"))) return true;
        return existsSync(venvPy) && venvPy.toLowerCase().endsWith("\\scripts\\python.exe");
      },
      fix: () => "Remove %USERPROFILE%\\.arkaos\\venv and run: npx arkaos@latest update",
    }
  );
}

export async function doctor() {
  console.log("\n  ArkaOS Doctor — Health Checks\n");

  let passed = 0;
  let warned = 0;
  let failed = 0;

  for (const check of checks) {
    // A single check that throws must not crash the rest of the doctor.
    // Treat the exception as "check failed" and record a short hint so
    // the user can see what blew up. Also keep any stack-trace noise
    // out of the console output.
    let ok = false;
    let checkError = null;
    try {
      ok = !!check.check();
    } catch (err) {
      checkError = err && err.message ? String(err.message).split("\n")[0].slice(0, 120) : String(err);
    }

    const icon = ok
      ? "\x1b[32m\u2713\x1b[0m"
      : (check.severity === "fail" ? "\x1b[31m\u2717\x1b[0m" : "\x1b[33m!\x1b[0m");
    console.log(`  ${icon}  ${check.description}`);

    if (!ok) {
      if (checkError) {
        console.log(`     Error: ${checkError}`);
      }
      let fixHint;
      try {
        fixHint = check.fix();
      } catch (err) {
        fixHint = "(fix hint unavailable)";
      }
      console.log(`     Fix: ${fixHint}`);
      if (check.severity === "fail") failed++;
      else warned++;
    } else {
      passed++;
    }
  }

  console.log(`\n  Results: ${passed} passed, ${warned} warnings, ${failed} failures\n`);
  if (failed > 0) process.exit(1);
}
