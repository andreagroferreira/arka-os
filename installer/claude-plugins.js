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

// Third-party marketplaces that must be registered (via
// `claude plugin marketplace add <repo>`) before their plugins can be
// installed. Each entry is a GitHub `owner/repo` shorthand.
export const DEFAULT_CLAUDE_MARKETPLACES = [
  "nextlevelbuilder/ui-ux-pro-max-skill",
  // F2-7b: the ArkaOS marketplace itself — registered by GitHub
  // owner/repo (NEVER a directory source anchored on the volatile npx
  // cache). Registration costs zero context; the 16 per-department
  // plugins stay opt-in pure (`/plugin install arkaos-<dept>@arkaos`),
  // so DEFAULT_CLAUDE_PLUGINS deliberately does NOT change.
  "andreagroferreira/arka-os",
];

// Each entry is "name@marketplace" matching the `claude plugin install`
// CLI argument format.
export const DEFAULT_CLAUDE_PLUGINS = [
  "frontend-design@claude-plugins-official",
  "ui-ux-pro-max@ui-ux-pro-max-skill",
];

const _INSTALLED_REGISTRY = join(
  homedir(), ".claude", "plugins", "installed_plugins.json",
);

export function installDefaultClaudePlugins({
  runtime = "claude-code",
  plugins = DEFAULT_CLAUDE_PLUGINS,
  marketplaces = DEFAULT_CLAUDE_MARKETPLACES,
  home = homedir(),
} = {}) {
  if (runtime !== "claude-code") {
    return { skipped: "runtime-not-claude-code", results: [], marketplaces: [] };
  }
  if (!isClaudeCliAvailable()) {
    return { skipped: "claude-cli-not-found", results: [], marketplaces: [] };
  }
  // Marketplaces must be registered before their plugins can resolve.
  const marketplaceResults = marketplaces.map((m) => addMarketplace(m));
  const alreadyInstalled = readInstalledRegistry(home);
  const results = plugins.map((p) =>
    installOne(p, alreadyInstalled),
  );
  return { skipped: null, results, marketplaces: marketplaceResults };
}

// Register a third-party plugin marketplace. Idempotent and never-throws:
// a marketplace that is already known is reported as already-present.
function addMarketplace(marketplace) {
  const out = spawnSync("claude", ["plugin", "marketplace", "add", marketplace], {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  if (out.status === 0) {
    return { marketplace, action: "added" };
  }
  const msg = (out.stderr || out.error?.message || "").toLowerCase();
  if (msg.includes("already") || msg.includes("exists")) {
    return { marketplace, action: "already-present" };
  }
  return { marketplace, action: "failed", reason: msg.trim().slice(0, 200) };
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
