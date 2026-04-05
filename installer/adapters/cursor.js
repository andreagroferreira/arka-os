import { existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

export default {
  configureHooks(config, installDir) {
    // Cursor uses .cursorrules for project-level instructions
    // and .cursor/rules for global rules
    const rulesDir = join(config.configDir, "rules");
    mkdirSync(rulesDir, { recursive: true });

    const arkaosRule = `# ArkaOS v2 Configuration

ArkaOS is installed at: ${installDir}

## Instructions

You are running inside ArkaOS — The Operating System for AI Agent Teams.
Load full instructions from: ${join(installDir, "config", "cursor-instructions.md")}

## Available Commands

Use natural language or prefix commands:
- /do <description> — Universal orchestrator
- /dev, /mkt, /fin, /strat, /brand, /ops, /ecom, /kb, /saas, /landing, /community, /content

## Agent System

ArkaOS has 62 specialized agents across 16 departments. Each request is routed to the appropriate squad.
`;

    writeFileSync(join(rulesDir, "arkaos.md"), arkaosRule);
    console.log("         Cursor rules configured.");
  },
};
