import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";

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

    // UserPromptSubmit — Synapse v2 context injection
    settings.hooks.UserPromptSubmit = [
      {
        hooks: [
          {
            type: "command",
            command: join(hooksDir, "user-prompt-submit.sh"),
            timeout: 10,
          },
        ],
      },
    ];

    // PostToolUse — Error tracking
    settings.hooks.PostToolUse = [
      {
        hooks: [
          {
            type: "command",
            command: join(hooksDir, "post-tool-use.sh"),
            timeout: 5,
          },
        ],
      },
    ];

    // PreCompact — Session digest
    settings.hooks.PreCompact = [
      {
        hooks: [
          {
            type: "command",
            command: join(hooksDir, "pre-compact.sh"),
            timeout: 30,
          },
        ],
      },
    ];

    writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    console.log("         Claude Code hooks configured.");
  },
};
