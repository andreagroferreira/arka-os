import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export default {
  configureHooks(config, installDir) {
    const settingsPath = config.settingsFile;

    let settings = {};
    if (existsSync(settingsPath)) {
      try {
        settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
      } catch {
        settings = {};
      }
    }

    // Configure status line
    if (!settings.statusLine) {
      settings.statusLine = {
        type: "command",
        command: join(installDir, "config", "statusline.sh"),
        padding: 2,
      };
    }

    // Configure hooks
    if (!settings.hooks) {
      settings.hooks = {};
    }

    const hooksDir = join(installDir, "config", "hooks");

    // UserPromptSubmit — Synapse context injection
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
