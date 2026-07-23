import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { listBundleFiles, readBundleFile } from "../harness-bundle.js";

/**
 * OpenCode adapter (Foundation PR-6). Deploys the generated harness
 * bundle onto OpenCode's native surfaces (opencode.ai/docs):
 *
 *   AGENTS.md      instructions contract (same body as codex)
 *   agents/*.md    curated agent cut (C-suite + squad leads), with the
 *                  agent-YAML model tier resolved onto the user's own
 *                  opencode model/small_model (agents-meta.json sidecar)
 *   commands/*.md  one /arka-<dept> router command per department
 *   plugins/arka.ts  governance plugin (kb-first/frontend/compliance gates)
 *   opencode.json  arka-tools MCP + seeded user MCPs — merged
 *                  NON-destructively
 *
 * Merge contract: user keys ALWAYS win. An existing `$schema`, any
 * user-defined `mcp` server, or a user-modified `arka-tools` entry is
 * never overwritten; a corrupt opencode.json is never clobbered (we
 * skip with a warning instead — config-seed.js posture).
 */

/**
 * Pure, exported for tests. Returns:
 *   { config, changed }  merged object + whether anything was added
 *   null                 leave the file alone (corrupt input)
 */
export function mergeOpencodeConfig(existingText, fragmentText) {
  let fragment;
  try {
    fragment = JSON.parse(fragmentText);
  } catch {
    return null;
  }
  let existing = {};
  const trimmed = (existingText ?? "").trim();
  if (trimmed !== "") {
    try {
      existing = JSON.parse(trimmed);
    } catch {
      return null; // corrupt user config — never clobber
    }
    if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
      return null;
    }
  }
  const merged = { ...existing };
  let changed = false;
  if (!merged.$schema && fragment.$schema) {
    merged.$schema = fragment.$schema;
    changed = true;
  }
  const userMcp =
    merged.mcp && typeof merged.mcp === "object" && !Array.isArray(merged.mcp)
      ? merged.mcp
      : {};
  const mcp = { ...userMcp };
  for (const [name, server] of Object.entries(fragment.mcp || {})) {
    if (!(name in mcp)) {
      mcp[name] = server;
      changed = true;
    }
  }
  if (changed && Object.keys(mcp).length > 0) merged.mcp = mcp;
  return { config: merged, changed };
}

/** Expand leading `~` in command arrays / env values (pure, testable). */
export function expandHome(value) {
  if (typeof value === "string") {
    return value.startsWith("~/") ? join(homedir(), value.slice(2)) : value;
  }
  if (Array.isArray(value)) return value.map(expandHome);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, expandHome(v)])
    );
  }
  return value;
}

/**
 * User-local MCPs seeded from ArkaOS state (never in the static bundle —
 * paths/endpoints differ per machine). Returns only entries the user
 * config does NOT already define.
 */
export function userLocalMcpSeeds(existingMcp) {
  const home = homedir();
  const seeds = {};
  try {
    const profile = JSON.parse(
      readFileSync(join(home, ".arkaos", "profile.json"), "utf-8")
    );
    if (profile.vaultPath && existsSync(profile.vaultPath)) {
      seeds.obsidian = {
        type: "local",
        command: ["npx", "-y", "@bitbonsai/mcpvault@latest", profile.vaultPath],
        enabled: true,
      };
    }
  } catch {}
  try {
    const arkaConfig = JSON.parse(
      readFileSync(join(home, ".arkaos", "config.json"), "utf-8")
    );
    const graphify = arkaConfig?.knowledge?.graphify;
    if (graphify?.enabled && graphify?.url) {
      let headers = graphify.headers;
      if (!headers) {
        try {
          const claude = JSON.parse(
            readFileSync(join(home, ".claude.json"), "utf-8")
          );
          const raw = claude?.mcpServers?.graphify?.headers;
          if (raw) {
            headers = Object.fromEntries(
              Object.entries(raw).map(([k, v]) => [
                k,
                String(v).replace(/^Bearer\s+Bearer\s+/i, "Bearer "),
              ])
            );
          }
        } catch {}
      }
      seeds.graphify = {
        type: "remote",
        url: graphify.url,
        ...(headers ? { headers } : {}),
        enabled: true,
      };
    }
  } catch {}
  return Object.fromEntries(
    Object.entries(seeds).filter(([name]) => !(name in (existingMcp || {})))
  );
}

/**
 * Inject `model:` into a deployed agent file's frontmatter, mapping the
 * ArkaOS tier onto the user's own opencode models. Skips when the file
 * already pins a model or no model is configured.
 */
export function injectAgentModel(content, tier, mainModel, smallModel) {
  if (!mainModel || /^model:/m.test(content)) return content;
  const resolved = tier === "haiku" ? smallModel || mainModel : mainModel;
  if (!resolved) return content;
  return content.replace(/^---\n/, `---\nmodel: ${resolved}\n`);
}

export default {
  configureHooks(config) {
    // OpenCode has no shell-hook chain; "configure" means deploying the
    // instruction/agent/command surfaces + the MCP config merge.
    const agentsMd = readBundleFile("opencode", "AGENTS.md");
    if (!agentsMd) {
      console.warn(
        "         OpenCode bundle missing (harness/opencode/) — " +
          "run scripts/harness_gen.py; skipping."
      );
      return;
    }
    mkdirSync(config.configDir, { recursive: true });
    writeFileSync(join(config.configDir, "AGENTS.md"), agentsMd);

    const existingText = existsSync(config.settingsFile)
      ? readFileSync(config.settingsFile, "utf-8")
      : "";
    let existingConfig = {};
    try {
      existingConfig = existingText.trim() ? JSON.parse(existingText) : {};
    } catch {
      existingConfig = {};
    }

    let agentsMeta = {};
    try {
      agentsMeta = JSON.parse(
        readBundleFile("opencode", "agents-meta.json") || "{}"
      );
    } catch {
      agentsMeta = {};
    }

    let deployed = 0;
    for (const sub of ["agents", "commands"]) {
      const names = listBundleFiles("opencode", sub);
      if (names.length === 0) continue;
      mkdirSync(join(config.configDir, sub), { recursive: true });
      for (const name of names) {
        let content = readBundleFile("opencode", `${sub}/${name}`);
        if (content === null) continue;
        if (sub === "agents" && agentsMeta[name]) {
          content = injectAgentModel(
            content,
            agentsMeta[name],
            existingConfig.model,
            existingConfig.small_model
          );
        }
        writeFileSync(join(config.configDir, sub, name), content);
        deployed += 1;
      }
    }

    const plugin = readBundleFile("opencode", "plugins/arka.ts");
    if (plugin !== null) {
      mkdirSync(join(config.configDir, "plugins"), { recursive: true });
      writeFileSync(join(config.configDir, "plugins", "arka.ts"), plugin);
      deployed += 1;
    }

    const fragment = readBundleFile("opencode", "opencode.json");
    if (fragment) {
      const expanded = JSON.stringify(expandHome(JSON.parse(fragment)));
      const result = mergeOpencodeConfig(existingText, expanded);
      if (result === null) {
        console.warn(
          "         opencode.json unreadable — left untouched " +
            "(the merge is never destructive)."
        );
      } else {
        const seeds = userLocalMcpSeeds(result.config.mcp || {});
        if (Object.keys(seeds).length > 0) {
          result.config.mcp = { ...(result.config.mcp || {}), ...seeds };
          result.changed = true;
        }
        if (result.changed) {
          writeFileSync(
            config.settingsFile,
            JSON.stringify(result.config, null, 2) + "\n"
          );
          console.log(
            "         opencode.json updated (arka MCPs registered, user keys preserved)."
          );
        }
      }
    }
    console.log(
      `         OpenCode configured (AGENTS.md + ${deployed} agent/command/plugin files).`
    );
  },
};
