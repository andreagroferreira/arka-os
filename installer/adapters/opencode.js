import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { listBundleFiles, readBundleFile } from "../harness-bundle.js";

/**
 * OpenCode adapter (Foundation PR-6). Deploys the generated harness
 * bundle onto OpenCode's native surfaces (opencode.ai/docs):
 *
 *   AGENTS.md      instructions contract (same body as codex)
 *   agents/*.md    curated agent cut (C-suite + squad leads)
 *   commands/*.md  one /arka-<dept> router command per department
 *   opencode.json  arka-tools MCP — merged NON-destructively
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

    let deployed = 0;
    for (const sub of ["agents", "commands"]) {
      const names = listBundleFiles("opencode", sub);
      if (names.length === 0) continue;
      mkdirSync(join(config.configDir, sub), { recursive: true });
      for (const name of names) {
        const content = readBundleFile("opencode", `${sub}/${name}`);
        if (content === null) continue;
        writeFileSync(join(config.configDir, sub, name), content);
        deployed += 1;
      }
    }

    const fragment = readBundleFile("opencode", "opencode.json");
    if (fragment) {
      const existingText = existsSync(config.settingsFile)
        ? readFileSync(config.settingsFile, "utf-8")
        : "";
      const result = mergeOpencodeConfig(existingText, fragment);
      if (result === null) {
        console.warn(
          "         opencode.json unreadable — left untouched " +
            "(the merge is never destructive)."
        );
      } else if (result.changed) {
        writeFileSync(
          config.settingsFile,
          JSON.stringify(result.config, null, 2) + "\n"
        );
        console.log(
          "         opencode.json updated (arka-tools MCP registered, user keys preserved)."
        );
      }
    }
    console.log(
      `         OpenCode configured (AGENTS.md + ${deployed} agent/command files).`
    );
  },
};
