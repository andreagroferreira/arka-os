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
    "no-system": { type: "boolean" },
    "with-ollama": { type: "boolean" },
    // PR3.5 v3.74.1 — declared so `npx arkaos doctor --fix` lands in
    // `values.fix` rather than as a free positional under strict:false.
    // Eliminates the dead-branch fallback flagged by Marta in PR2's QG.
    fix: { type: "boolean" },
    // Model Fabric PR-A — `npx arkaos models [--json] [set ... --effort max]`
    json: { type: "boolean" },
    effort: { type: "string" },
    // Fusion — `npx arkaos fusion [--save|--show] "question"`
    save: { type: "boolean" },
    show: { type: "boolean" },
    // F2-7a — `npx arkaos mcp start [--write]`. Declared so it lands in
    // `values.write` instead of a free positional under strict:false
    // (the documented --fix lesson).
    write: { type: "boolean" },
    // F2-7c — `npx arkaos update --skills <curated|full>` (same
    // strict:false declaration requirement).
    skills: { type: "string" },
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
  npx arkaos migrate-user-data  Move user data (~/.claude/skills/arka/ → ~/.arkaos/)
  npx arkaos dashboard        Start monitoring dashboard
  npx arkaos autostart <enable|disable|status>  Start dashboard on boot
  npx arkaos keys             Manage API keys (OpenAI, fal.ai, etc.)
  npx arkaos models           Model Fabric: which model runs each role
  npx arkaos models set <role> <provider>/<model>  Re-route a role
  npx arkaos mcp start        Start the arka-tools MCP server (stdio; --write enables writes)
  npx arkaos update --skills <curated|full>  Choose the deployed skill set (default: curated on fresh installs)
  npx arkaos shield           Scan the harness config for vulnerabilities (--json)
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
  npx arkaos shield                     Scan the harness config (exit 2 = critical)
  npx arkaos shield --json              Machine-readable, for CI
`);
  process.exit(0);
}

async function main() {
  switch (command) {
    case "install":
      const runtime = values.runtime || await detectRuntime();
      await install({
        runtime,
        path: values.path,
        force: values.force,
        skipSystem: values["no-system"],
        withOllama: values["with-ollama"],
      });
      break;

    case "init": {
      const { init } = await import("./init.js");
      await init({ path: values.path || process.cwd() });
      break;
    }

    case "doctor": {
      const { doctor } = await import("./doctor.js");
      await doctor({ fix: values.fix === true, json: values.json === true });
      break;
    }

    case "update": {
      const { update } = await import("./update.js");
      await update({ skillsFlag: values.skills || "" });
      break;
    }

    case "autostart": {
      const { autostart } = await import("./autostart.js");
      await autostart(positionals.slice(1));
      break;
    }

    case "uninstall":
      const { uninstall } = await import("./uninstall.js");
      await uninstall();
      break;

    case "migrate":
      const { migrate } = await import("./migrate.js");
      await migrate();
      break;

    case "migrate-user-data": {
      const { migrateUserData, printMigrationReport } = await import("./migrate-user-data.js");
      printMigrationReport(migrateUserData());
      break;
    }

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
        : `bash "${join(repoRootDash, "scripts", "start-dashboard.sh")}"`;
      try {
        execDash(dashCmd, {
          stdio: "inherit",
          env: { ...process.env, ARKAOS_ROOT: repoRootDash },
        });
      } catch { process.exit(1); }
      break;
    }

    case "models": {
      const { execSync } = await import("node:child_process");
      const repoRootModels = join(__dirname, "..");
      const pyModels = getArkaosPython();
      if (!pyModels) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      const modelArgs = positionals.slice(1).map((a) => `"${a}"`).join(" ");
      const effortFlag = values.effort ? ` --effort "${values.effort}"` : "";
      const jsonFlag = values.json ? " --json" : "";
      try {
        execSync(`"${pyModels}" -m core.runtime.model_router_cli ${modelArgs}${effortFlag}${jsonFlag}`, {
          stdio: "inherit",
          cwd: repoRootModels,
          env: { ...process.env, ARKAOS_ROOT: repoRootModels, PYTHONPATH: repoRootModels },
        });
      } catch { process.exit(1); }
      break;
    }

    case "fusion": {
      const { execSync } = await import("node:child_process");
      const repoRootFusion = join(__dirname, "..");
      const pyFusion = getArkaosPython();
      if (!pyFusion) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      const fusionArgs = positionals.slice(1).map((a) => `"${a}"`).join(" ");
      const saveFlag = values.save ? " --save" : "";
      const showFlag = values.show ? " --show" : "";
      try {
        execSync(`"${pyFusion}" -m core.fusion.cli${saveFlag}${showFlag} ${fusionArgs}`, {
          stdio: "inherit",
          cwd: repoRootFusion,
          env: { ...process.env, ARKAOS_ROOT: repoRootFusion, PYTHONPATH: repoRootFusion },
        });
      } catch { process.exit(1); }
      break;
    }

    case "shield": {
      // The harness config as attack surface. Exit code is the contract
      // CI gates on (0 = A/B, 1 = C/D, 2 = F or any CRITICAL), so the
      // child's code is propagated verbatim rather than collapsed to 1.
      const { spawnSync } = await import("node:child_process");
      const repoRootShield = join(__dirname, "..");
      const pyShield = getArkaosPython();
      if (!pyShield) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      const shieldArgs = process.argv.slice(3);
      const shieldRun = spawnSync(
        pyShield,
        ["-m", "core.governance.harness_scanner_cli", ...shieldArgs],
        {
          stdio: "inherit",
          cwd: process.cwd(),
          env: { ...process.env, ARKAOS_ROOT: repoRootShield, PYTHONPATH: repoRootShield },
        }
      );
      process.exit(shieldRun.status === null ? 1 : shieldRun.status);
    }

    case "index": {
      const { execFileSync } = await import("node:child_process");
      const repoRoot = join(__dirname, "..");
      const pyIndex = getArkaosPython();
      if (!pyIndex) { console.error("No Python found. Run: npx arkaos install"); process.exit(1); }
      try {
        // argv array, not a joined string: vault paths with spaces
        // ("C:\Users\Ana Maria\vault") broke the quoted-string form.
        execFileSync(pyIndex, [join(repoRoot, "scripts", "knowledge-index.py"), ...positionals.slice(1)], {
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

    case "mcp": {
      const verb = positionals[1];
      if (verb !== "start") {
        console.error('Usage: npx arkaos mcp start [--write]');
        process.exit(1);
      }
      const { startServer } = await import("./mcp-runner.js");
      process.exit(startServer({ write: Boolean(values.write) }));
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
