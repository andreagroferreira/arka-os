import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { platform } from "node:os";
import { fileURLToPath } from "node:url";

const IS_WINDOWS = platform() === "win32";
const ARKAOS_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

/**
 * Deploy the packaged Quality Gate / squad-lead subagent definitions
 * (`config/claude-agents/*.md` in the ArkaOS package: marta-cqo,
 * eduardo-copy, francisca-tech, paulo-tech-lead) into a project's
 * `.claude/agents/` directory, so Claude Code can dispatch them as real
 * subagent types with structured QGVerdict output (PR-4 evidence
 * Quality Gate). Source lives under config/ because `.claude/` is
 * gitignored in the ArkaOS repo itself.
 *
 * Same merge philosophy as configureHooks: never delete user files,
 * overwrite only the ArkaOS-owned definitions by name. Best-effort —
 * a missing source dir (older package) is a silent no-op.
 *
 * @param {string} projectDir - project root (contains or gets .claude/)
 * @param {string} [sourceRoot] - override for tests; defaults to package root
 * @returns {number} count of agent definitions deployed
 */
export function deployProjectAgents(projectDir, sourceRoot = ARKAOS_ROOT) {
  const agentsSrc = join(sourceRoot, "config", "claude-agents");
  if (!existsSync(agentsSrc)) return 0;

  const agentsDest = join(projectDir, ".claude", "agents");
  let deployed = 0;
  try {
    mkdirSync(agentsDest, { recursive: true });
    for (const file of readdirSync(agentsSrc)) {
      if (!file.endsWith(".md")) continue;
      const srcFile = join(agentsSrc, file);
      try {
        if (!statSync(srcFile).isFile()) continue;
        copyFileSync(srcFile, join(agentsDest, file));
        deployed++;
      } catch {
        // Best-effort — a single unreadable agent file shouldn't break init.
      }
    }
  } catch {
    return deployed;
  }
  return deployed;
}

/**
 * Build a complete inner hook-entry object for Claude Code's settings.json.
 *
 * On Unix we point `command` directly at the `.sh` script and rely on the
 * shebang for interpreter selection; no `shell` field is needed because
 * Claude Code's default is `bash`.
 *
 * On Windows we point `command` at the `.ps1` script and set the
 * documented `shell: "powershell"` hook field so Claude Code spawns
 * PowerShell directly and pipes the hook payload to the script's stdin
 * natively. This is the pattern prescribed by the upstream hooks
 * reference at https://code.claude.com/docs/en/hooks :
 *
 *     shell (no, optional): Shell to use for this hook. Accepts
 *     "bash" (default) or "powershell". Setting "powershell" runs the
 *     command via PowerShell on Windows. Does not require
 *     CLAUDE_CODE_USE_POWERSHELL_TOOL since hooks spawn PowerShell
 *     directly.
 *
 * Earlier versions of this adapter embedded the full
 * `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ...`
 * command line in `command` without setting `shell`. Claude Code then
 * defaulted to `shell: "bash"`, which on Windows routes through a
 * compatibility layer that drops the stdin pipe before the PowerShell
 * script reads it. `SessionStart` still appeared to work (it only
 * writes stdout), but every other hook received a 0-byte stdin, hit
 * the `IsNullOrWhiteSpace` guard at the top of each `.ps1`, and
 * silently exited. This commit fixes that by emitting the canonical
 * `shell: "powershell"` field and letting Claude Code handle the
 * PowerShell invocation itself.
 */
function hookEntry(hooksDir, name, timeout) {
  if (IS_WINDOWS) {
    return {
      type: "command",
      command: join(hooksDir, `${name}.ps1`),
      shell: "powershell",
      timeout,
    };
  }
  return {
    type: "command",
    command: join(hooksDir, `${name}.sh`),
    timeout,
  };
}

export default {
  configureHooks(config, installDir) {
    const settingsPath = config.settingsFile;

    // Ensure settings directory exists
    mkdirSync(dirname(settingsPath), { recursive: true });

    // Load existing settings (merge, don't overwrite)
    let settings = {};
    if (existsSync(settingsPath)) {
      try {
        settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
      } catch {
        // Backup corrupted settings
        const backup = settingsPath + ".bak";
        try { writeFileSync(backup, readFileSync(settingsPath)); } catch {}
        settings = {};
      }
    }

    const hooksDir = join(installDir, "config", "hooks");

    // Configure hooks (ArkaOS hooks only — preserve user's other hooks)
    if (!settings.hooks) {
      settings.hooks = {};
    }

    // SessionStart — Branded greeting + version drift detection
    // Timeout 15s: PowerShell cold-start on Windows VMs can exceed 5s.
    settings.hooks.SessionStart = [
      { hooks: [hookEntry(hooksDir, "session-start", 15)] },
    ];

    // UserPromptSubmit — Synapse v2 context injection
    settings.hooks.UserPromptSubmit = [
      { hooks: [hookEntry(hooksDir, "user-prompt-submit", 10)] },
    ];

    // PostToolUse — Error tracking
    settings.hooks.PostToolUse = [
      { hooks: [hookEntry(hooksDir, "post-tool-use", 5)] },
    ];

    // PreToolUse — Flow enforcement gate (gated by hooks.hardEnforcement
    // feature flag in ~/.arkaos/config.json; no-op when flag is false).
    settings.hooks.PreToolUse = [
      { hooks: [hookEntry(hooksDir, "pre-tool-use", 10)] },
    ];

    // Stop — Flow completion validator (WARN mode in v2.20.0; promotion
    // to STRICT mode is gated on ≥ 2 weeks of clean telemetry per ADR
    // 2026-04-17-binding-flow-enforcement).
    settings.hooks.Stop = [
      { hooks: [hookEntry(hooksDir, "stop", 5)] },
    ];

    // PreCompact — Session digest
    settings.hooks.PreCompact = [
      { hooks: [hookEntry(hooksDir, "pre-compact", 30)] },
    ];

    // CwdChanged — Project/ecosystem auto-detection
    settings.hooks.CwdChanged = [
      { hooks: [hookEntry(hooksDir, "cwd-changed", 5)] },
    ];

    // Statusline — ArkaOS branded status bar
    // Claude Code reads the camelCase "statusLine" key; the lowercase
    // "statusline" variant is silently ignored.
    const configDir = join(installDir, "config");
    const statuslineFile = IS_WINDOWS ? "statusline.ps1" : "statusline.sh";
    const statuslinePath = join(configDir, statuslineFile);
    if (existsSync(statuslinePath)) {
      const command = IS_WINDOWS
        ? `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${statuslinePath}"`
        : statuslinePath;
      settings.statusLine = {
        type: "command",
        command,
        padding: 2,
      };
    }

    writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log("         Claude Code hooks configured.");
  },
};
