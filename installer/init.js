import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, basename } from "node:path";
import { execSync } from "node:child_process";

export async function init({ path }) {
  const projectDir = path || process.cwd();
  const configPath = join(projectDir, ".arkaos.json");
  const projectName = basename(projectDir);

  console.log(`\n  ArkaOS Project Init — ${projectName}\n`);

  // Detect existing config
  if (existsSync(configPath)) {
    const existing = JSON.parse(readFileSync(configPath, "utf-8"));
    console.log(`  Config already exists: ${configPath}`);
    console.log(`  Department: ${existing.department || "auto"}`);
    console.log(`  Stack: ${existing.stack || "auto"}`);
    console.log(`\n  To reconfigure, delete .arkaos.json and run again.\n`);
    return;
  }

  // Auto-detect stack
  const stack = detectStack(projectDir);
  console.log(`  Detected stack: ${stack}`);

  // Auto-detect department
  const department = detectDepartment(projectDir, stack);
  console.log(`  Default department: ${department}`);

  // Create config
  const config = {
    name: projectName,
    department,
    stack,
    created: new Date().toISOString(),
    arkaos_version: "2",
    settings: {
      quality_gate: true,
      obsidian_output: true,
      auto_index: true,
    },
  };

  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  console.log(`  Created: ${configPath}`);

  // Create .claude/settings.local.json if Claude Code project
  const claudeDir = join(projectDir, ".claude");
  const localSettings = join(claudeDir, "settings.local.json");
  if (!existsSync(localSettings)) {
    mkdirSync(claudeDir, { recursive: true });
    writeFileSync(localSettings, JSON.stringify({
      permissions: {},
      hooks: {},
    }, null, 2) + "\n");
    console.log(`  Created: .claude/settings.local.json`);
  }

  console.log(`
  Project initialized for ArkaOS.

  Config: .arkaos.json
  Stack:  ${stack}
  Dept:   ${department}

  ArkaOS will auto-detect this project's context via Synapse L3.
  Use /dev, /mkt, /brand etc. or just describe what you need.
  `);
}

function detectStack(dir) {
  if (existsSync(join(dir, "composer.json"))) return "laravel";
  if (existsSync(join(dir, "nuxt.config.ts")) || existsSync(join(dir, "nuxt.config.js"))) return "nuxt";
  if (existsSync(join(dir, "next.config.js")) || existsSync(join(dir, "next.config.ts")) || existsSync(join(dir, "next.config.mjs"))) return "nextjs";
  if (existsSync(join(dir, "vite.config.ts"))) {
    try {
      const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf-8"));
      if (pkg.dependencies?.vue) return "vue";
      if (pkg.dependencies?.react) return "react";
    } catch {}
    return "vite";
  }
  if (existsSync(join(dir, "package.json"))) {
    try {
      const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf-8"));
      if (pkg.dependencies?.react) return "react";
      if (pkg.dependencies?.vue) return "vue";
      if (pkg.dependencies?.express) return "node-express";
      return "node";
    } catch {}
  }
  if (existsSync(join(dir, "pyproject.toml")) || existsSync(join(dir, "setup.py"))) return "python";
  if (existsSync(join(dir, "Gemfile"))) return "ruby";
  if (existsSync(join(dir, "go.mod"))) return "go";
  if (existsSync(join(dir, "Cargo.toml"))) return "rust";
  return "unknown";
}

function detectDepartment(dir, stack) {
  // Code projects default to dev
  if (["laravel", "nuxt", "nextjs", "react", "vue", "node", "python", "ruby", "go", "rust", "node-express", "vite"].includes(stack)) {
    return "dev";
  }
  return "general";
}
