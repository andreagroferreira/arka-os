// Integrity tests for the MCP registry + per-stack profiles.
//
// Guards two invariants that the frontend-tooling work depends on:
//   1. The `magic` MCP is registered, env-gated by MAGIC_API_KEY, and wired
//      into every frontend stack profile (mandatory for frontend UI/UX).
//   2. No profile references an MCP key that the registry does not define.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MCPS_DIR = join(ROOT, "mcps");

const registry = JSON.parse(readFileSync(join(MCPS_DIR, "registry.json"), "utf-8"));
const registryKeys = new Set(Object.keys(registry.mcpServers));

const FRONTEND_PROFILES = ["nuxt", "vue", "react", "nextjs", "full-stack"];

function loadProfile(name) {
  return JSON.parse(readFileSync(join(MCPS_DIR, "profiles", `${name}.json`), "utf-8"));
}


// ─── Magic MCP registry entry ───────────────────────────────────────────


test("registry defines the magic MCP", () => {
  assert.ok(registryKeys.has("magic"), "registry.json must define a `magic` server");
});

test("magic MCP is env-gated by MAGIC_API_KEY", () => {
  const magic = registry.mcpServers.magic;
  assert.deepEqual(magic.required_env, ["MAGIC_API_KEY"]);
  assert.equal(magic.env.API_KEY, "${MAGIC_API_KEY}");
});

test("magic MCP does NOT hardcode a literal API key", () => {
  // Hard guardrail: the operator's key must never be committed. The only
  // legal env value is the ${MAGIC_API_KEY} placeholder.
  assert.equal(registry.mcpServers.magic.env.API_KEY, "${MAGIC_API_KEY}");
});

test("registry.json contains no leaked literal secret (hex key)", () => {
  // A 21st.dev/most API keys are long hex/opaque strings. The registry
  // must never ship one — every secret is a ${PLACEHOLDER}.
  const raw = readFileSync(join(MCPS_DIR, "registry.json"), "utf-8");
  assert.doesNotMatch(raw, /[a-f0-9]{32,}/i,
    "registry.json must not contain a literal secret — use ${PLACEHOLDER}");
});


// ─── Magic wired into every frontend profile ────────────────────────────


for (const name of FRONTEND_PROFILES) {
  test(`profile '${name}' includes the magic MCP`, () => {
    const profile = loadProfile(name);
    assert.ok(
      profile.mcps.includes("magic"),
      `frontend profile ${name} must include magic (mandatory for UI/UX)`,
    );
  });
}


// ─── No dangling MCP references across all profiles ─────────────────────


test("every profile references only MCPs defined in the registry", () => {
  const profileFiles = readdirSync(join(MCPS_DIR, "profiles")).filter((f) => f.endsWith(".json"));
  for (const file of profileFiles) {
    const profile = JSON.parse(readFileSync(join(MCPS_DIR, "profiles", file), "utf-8"));
    for (const mcp of profile.mcps || []) {
      assert.ok(
        registryKeys.has(mcp),
        `profile ${file} references unknown MCP '${mcp}'`,
      );
    }
  }
});
