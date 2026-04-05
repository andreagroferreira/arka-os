#!/usr/bin/env node

import { parseArgs } from "node:util";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { install } from "./index.js";
import { detectRuntime } from "./detect-runtime.js";

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
  npx arkaos update           Update to latest version
  npx arkaos migrate          Migrate from v1 to v2
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
