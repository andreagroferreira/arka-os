#!/usr/bin/env node

import { parseArgs } from "node:util";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { install } from "./index.js";
import { detectRuntime } from "./detect-runtime.js";
import { IS_WINDOWS } from "./platform.js";
import { getArkaosPython } from "./python-resolver.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const VERSION = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf-8")).version;

const { values, positionals } = parseArgs({
  options: {
    help: { type: "boolean", short: "h" },
    version: { type: "boolean", short: "v" },
    runtime: { type: "string", short: "r" },
    path: { type: "string", short: "p" },
    force: { type: "boolean", short: "f" },
  },
  allowPositionals: true,
  strict: false,
});

const command = positionals[0] || "install";

if (values.version) {
  console.log(`ArkaOS v${VERSION}`);
  process.exit(0);
}

if (values.help || command === "help") {
  console.log(`
ArkaOS v${VERSION} — The Operating System for AI Agent Teams

Usage:
  npx arkaos install          Install ArkaOS in current environment
  npx arkaos install --runtime <runtime>  Install for specific runtime
  npx arkaos init             Initialize project config (.arkaos.json)
  npx arkaos update           Update to latest version
  npx arkaos migrate          Migrate from v1 to v2
  npx arkaos dashboard        Start monitoring dashboard
  npx arkaos keys             Manage API keys (OpenAI, fal.ai, etc.)
  npx arkaos doctor           Run health checks
  npx arkaos uninstall        Remove ArkaOS

Options:
  -r, --runtime <name>   Target runtime: claude-code, codex, gemini, cursor
  -p, --path <dir>       Installation directory (default: auto-detect)
  -f, --force            Force reinstall, overwriting existing files
  -v, --version          Show version
  -h, --help             Show this help

Runtimes:
  claude-code    Anthropic Claude Code CLI
  codex          OpenAI Codex CLI
  gemini         Google Gemini CLI
  cursor         Cursor AI IDE

Examples:
  npx arkaos install                    Auto-detect runtime and install
  npx arkaos install --runtime codex    Install for Codex CLI specifically
  npx arkaos index                     Index knowledge base (Obsidian vault)
  npx arkaos search "query"            Search indexed knowledge
  npx arkaos doctor                     Verify installation health
`);
  process.exit(0);
}

async function main() {
  switch (command) {
    case "install":
      const runtime = values.runtime || await detectRuntime();
      await install({ runtime, path: values.path, force: values.force });
      break;

    case "init": {
      const { init } = await import("./init.js");
      await init({ path: values.path || process.cwd() });
      break;
    }

    case "doctor":
      const { doctor } = await import("./doctor.js");
      await doctor();
      break;

    case "update":
      const { update } = await import("./update.js");
      await update();
      break;

    case "uninstall":
      const { uninstall } = await import("./uninstall.js");
      await uninstall();
      break;

    case "migrate":
      const { migrate } = await import("./migrate.js");
      await migrate();
      break;

    case "keys": {
      const { keys: keysCmd } = await import("./keys.js");
      await keysCmd(positionals.slice(1));
      break;
    }

    case "dashboard": {
      const { execSync: execDash } = await import("node:child_process");
      // join(__dirname, "..") is cross-platform; the previous regex
      // `/\/installer$/` used forward slashes and did not match the
      // Windows backslash-separated path, leaving repoRootDash pointing
      // at the installer directory instead of the repo root.
      const repoRootDash = join(__dirname, "..");
      const dashCmd = IS_WINDOWS
        ? `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${join(repoRootDash, "scripts", "start-dashboard.ps1")}"`
        : `bash "${repoRootDash}/scripts/start-dashboard.sh"`;
      try {
        execDash(dashCmd, {
          stdio: "inherit",
          env: { ...process.env, ARKAOS_ROOT: repoRootDash },
        });
      } catch { process.exit(1); }
      break;
    }

    case "index": {
      const { execSync } = await import("node:child_process");
      const indexArgs = positionals.slice(1).join(" ");
      const repoRoot = join(__dirname, "..");
      const pyIndex = getArkaosPython();
      if (!pyIndex) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      try {
        execSync(`"${pyIndex}" "${join(repoRoot, "scripts", "knowledge-index.py")}" ${indexArgs || ""}`, {
          stdio: "inherit",
          env: { ...process.env, ARKAOS_ROOT: repoRoot },
        });
      } catch { process.exit(1); }
      break;
    }

    case "search": {
      const { execSync } = await import("node:child_process");
      const query = positionals.slice(1).join(" ");
      if (!query) { console.error("Usage: npx arkaos search \"your query\""); process.exit(1); }
      const repoRoot2 = join(__dirname, "..");
      const pySearch = getArkaosPython();
      if (!pySearch) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      try {
        execSync(`"${pySearch}" "${join(repoRoot2, "scripts", "knowledge-index.py")}" --search "${query}"`, {
          stdio: "inherit",
          env: { ...process.env, ARKAOS_ROOT: repoRoot2 },
        });
      } catch { process.exit(1); }
      break;
    }

    default:
      console.error(`Unknown command: ${command}`);
      console.error('Run "npx arkaos help" for usage information.');
      process.exit(1);
  }
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
