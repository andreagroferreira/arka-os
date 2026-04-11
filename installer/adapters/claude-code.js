import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { platform } from "node:os";

const IS_WINDOWS = platform() === "win32";

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
