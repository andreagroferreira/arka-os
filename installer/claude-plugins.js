// Auto-install official Claude Code plugins on `npx arkaos install` and
// `npx arkaos@latest update` (PR43 v2.62.0).
//
// Behaviour:
//   - No-op when runtime is not Claude Code
//   - Idempotent: skips plugins already in
//     ~/.claude/plugins/installed_plugins.json
//   - Surfaces a one-line status per plugin (installed | already-present | failed)
//   - Never raises — install failures are logged but don't break the installer
//
// Plugin list is intentionally short. Add new defaults here when the
// operator decides a plugin should ship as a standard ArkaOS dependency.

import { existsSync, readFileSync } from "node:fs";
import { execSync, spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

// Each entry is "name@marketplace" matching the `claude plugin install`
// CLI argument format.
export const DEFAULT_CLAUDE_PLUGINS = [
  "frontend-design@claude-plugins-official",
];

const _INSTALLED_REGISTRY = join(
  homedir(), ".claude", "plugins", "installed_plugins.json",
);

export function installDefaultClaudePlugins({
  runtime = "claude-code",
  plugins = DEFAULT_CLAUDE_PLUGINS,
  home = homedir(),
} = {}) {
  if (runtime !== "claude-code") {
    return { skipped: "runtime-not-claude-code", results: [] };
  }
  if (!isClaudeCliAvailable()) {
    return { skipped: "claude-cli-not-found", results: [] };
  }
  const alreadyInstalled = readInstalledRegistry(home);
  const results = plugins.map((p) =>
    installOne(p, alreadyInstalled),
  );
  return { skipped: null, results };
}

function isClaudeCliAvailable() {
  try {
    execSync("claude --version", { stdio: "pipe", timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

function readInstalledRegistry(home) {
  const path = join(home, ".claude", "plugins", "installed_plugins.json");
  if (!existsSync(path)) {
    return new Set();
  }
  try {
    const data = JSON.parse(readFileSync(path, "utf-8"));
    return new Set(Object.keys(data.plugins || {}));
  } catch {
    return new Set();
  }
}

function installOne(plugin, alreadyInstalled) {
  if (alreadyInstalled.has(plugin)) {
    return { plugin, action: "already-present" };
  }
  // Use spawnSync so we can capture exit code without throwing on non-zero.
  // Pass --silent equivalents if available; otherwise default verbosity is OK
  // — the installer is interactive at install time.
  const out = spawnSync("claude", ["plugin", "install", plugin], {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  if (out.error || out.status !== 0) {
    const msg = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { plugin, action: "failed", reason: msg };
  }
  return { plugin, action: "installed" };
}
