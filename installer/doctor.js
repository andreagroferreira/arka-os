import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";

const INSTALL_DIR = join(homedir(), ".arkaos");

const checks = [
  {
    name: "install-dir",
    description: "ArkaOS installation directory exists",
    severity: "fail",
    check: () => existsSync(INSTALL_DIR),
    fix: "Run: npx arkaos install",
  },
  {
    name: "manifest",
    description: "Install manifest present",
    severity: "fail",
    check: () => existsSync(join(INSTALL_DIR, "install-manifest.json")),
    fix: "Run: npx arkaos install",
  },
  {
    name: "python",
    description: "Python 3.11+ available",
    severity: "fail",
    check: () => {
      try {
        const v = execSync("python3 --version 2>&1", { stdio: "pipe" }).toString();
        const m = v.match(/(\d+)\.(\d+)/);
        return m && parseInt(m[1]) >= 3 && parseInt(m[2]) >= 11;
      } catch { return false; }
    },
    fix: "Install Python 3.11+: https://python.org",
  },
  {
    name: "hooks-dir",
    description: "Hook scripts installed",
    severity: "fail",
    check: () => existsSync(join(INSTALL_DIR, "config", "hooks", "user-prompt-submit.sh")),
    fix: "Run: npx arkaos install --force",
  },
  {
    name: "constitution",
    description: "Constitution YAML present",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "config", "constitution.yaml")),
    fix: "Run: npx arkaos install --force",
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
    fix: "Run: npx arkaos install --force",
  },
  {
    name: "profile",
    description: "User profile exists",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "profile.json")),
    fix: "Run: npx arkaos install",
  },
  {
    name: "python-core",
    description: "Python core engine importable",
    severity: "warn",
    check: () => {
      try {
        execSync('python3 -c "from core.synapse.engine import SynapseEngine"', { stdio: "pipe" });
        return true;
      } catch { return false; }
    },
    fix: "Run: pip install -e <arkaos-root>",
  },
];

export async function doctor() {
  console.log("\n  ArkaOS Doctor — Health Checks\n");

  let passed = 0;
  let warned = 0;
  let failed = 0;

  for (const check of checks) {
    const ok = check.check();
    const icon = ok ? "\x1b[32m✓\x1b[0m" : (check.severity === "fail" ? "\x1b[31m✗\x1b[0m" : "\x1b[33m!\x1b[0m");
    console.log(`  ${icon}  ${check.description}`);
    if (!ok) {
      console.log(`     Fix: ${check.fix}`);
      if (check.severity === "fail") failed++;
      else warned++;
    } else {
      passed++;
    }
  }

  console.log(`\n  Results: ${passed} passed, ${warned} warnings, ${failed} failures\n`);
  if (failed > 0) process.exit(1);
}
