import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const RUNTIMES = [
  {
    id: "claude-code",
    name: "Claude Code",
    detect: () => {
      try {
        execSync("claude --version", { stdio: "pipe" });
        return true;
      } catch {
        return false;
      }
    },
    configDir: () => join(homedir(), ".claude"),
    skillsDir: () => join(homedir(), ".claude", "skills"),
    settingsFile: () => join(homedir(), ".claude", "settings.json"),
  },
  {
    id: "codex",
    name: "Codex CLI",
    detect: () => {
      try {
        execSync("codex --version", { stdio: "pipe" });
        return true;
      } catch {
        return false;
      }
    },
    configDir: () => join(homedir(), ".codex"),
    skillsDir: () => join(homedir(), ".codex", "skills"),
    settingsFile: () => join(homedir(), ".codex", "settings.json"),
  },
  {
    id: "gemini",
    name: "Gemini CLI",
    detect: () => {
      try {
        execSync("gemini --version", { stdio: "pipe" });
        return true;
      } catch {
        return existsSync(join(homedir(), ".gemini"));
      }
    },
    configDir: () => join(homedir(), ".gemini"),
    skillsDir: () => join(homedir(), ".gemini", "skills"),
    settingsFile: () => join(homedir(), ".gemini", "settings.json"),
  },
  {
    id: "cursor",
    name: "Cursor",
    detect: () => {
      try {
        execSync("cursor --version", { stdio: "pipe" });
        return true;
      } catch {
        const cursorPaths = [
          join(homedir(), ".cursor"),
          "/Applications/Cursor.app",
          join(homedir(), "AppData", "Local", "Programs", "cursor"),
        ];
        return cursorPaths.some((p) => existsSync(p));
      }
    },
    configDir: () => join(homedir(), ".cursor"),
    skillsDir: () => join(homedir(), ".cursor", "skills"),
    settingsFile: () => join(homedir(), ".cursor", "settings.json"),
  },
];

export async function detectRuntime() {
  console.log("Detecting AI runtime...\n");

  const detected = [];
  for (const runtime of RUNTIMES) {
    if (runtime.detect()) {
      detected.push(runtime);
      console.log(`  Found: ${runtime.name}`);
    }
  }

  if (detected.length === 0) {
    console.error(
      "\nNo supported AI runtime detected.\n" +
        "Install one of: Claude Code, Codex CLI, Gemini CLI, or Cursor\n" +
        "Or specify manually: npx arkaos install --runtime claude-code"
    );
    process.exit(1);
  }

  if (detected.length === 1) {
    console.log(`\nUsing: ${detected[0].name}\n`);
    return detected[0].id;
  }

  console.log(`\nMultiple runtimes found. Using: ${detected[0].name}`);
  console.log(
    `To install for a different runtime: npx arkaos install --runtime <name>\n`
  );
  return detected[0].id;
}

export function getRuntimeConfig(runtimeId) {
  const runtime = RUNTIMES.find((r) => r.id === runtimeId);
  if (!runtime) {
    throw new Error(
      `Unknown runtime: ${runtimeId}. Supported: ${RUNTIMES.map((r) => r.id).join(", ")}`
    );
  }
  return {
    id: runtime.id,
    name: runtime.name,
    configDir: runtime.configDir(),
    skillsDir: runtime.skillsDir(),
    settingsFile: runtime.settingsFile(),
  };
}

export { RUNTIMES };
