// Foundation PR-6 — OpenCode first-class.
//
// Part 1: runtime registration (getRuntimeConfig shape, homedir-based).
// Part 2: mergeOpencodeConfig — the NON-destructive contract: user keys
// always win, corrupt configs are never clobbered.
// Part 3: adapter deployment against the REAL committed bundle into a
// temp configDir — AGENTS.md + agents/ + commands/ + opencode.json.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync,
} from "node:fs";
import { tmpdir, homedir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { getRuntimeConfig } = await import(join(ROOT, "installer", "detect-runtime.js"));
const adapterModule = await import(join(ROOT, "installer", "adapters", "opencode.js"));
const { mergeOpencodeConfig } = adapterModule;
const adapter = adapterModule.default;
const { listBundleFiles } = await import(join(ROOT, "installer", "harness-bundle.js"));

// ── Part 1: runtime registration ───────────────────────────────────────

test("opencode runtime is registered with XDG-style paths under homedir", () => {
  const config = getRuntimeConfig("opencode");
  assert.equal(config.id, "opencode");
  assert.equal(config.name, "OpenCode");
  assert.equal(config.configDir, join(homedir(), ".config", "opencode"));
  assert.equal(config.settingsFile, join(homedir(), ".config", "opencode", "opencode.json"));
  assert.equal(config.skillsDir, join(homedir(), ".config", "opencode", "commands"));
});

// ── Part 2: mergeOpencodeConfig — user keys always win ─────────────────

const FRAGMENT = JSON.stringify({
  $schema: "https://opencode.ai/config.json",
  mcp: {
    "arka-tools": {
      type: "local",
      command: ["npx", "-y", "arkaos", "mcp", "start"],
      enabled: true,
    },
  },
});

test("merge into an empty/missing config adds schema + arka-tools", () => {
  for (const existing of ["", "   ", null, undefined]) {
    const result = mergeOpencodeConfig(existing, FRAGMENT);
    assert.ok(result && result.changed, `changed expected for ${JSON.stringify(existing)}`);
    assert.equal(result.config.$schema, "https://opencode.ai/config.json");
    assert.equal(result.config.mcp["arka-tools"].type, "local");
  }
});

test("user-defined servers and keys are preserved untouched", () => {
  const user = JSON.stringify({
    $schema: "https://example.com/user-schema.json",
    model: "anthropic/claude-sonnet",
    mcp: { "my-server": { type: "local", command: ["my-mcp"], enabled: true } },
  });
  const result = mergeOpencodeConfig(user, FRAGMENT);
  assert.ok(result.changed);
  assert.equal(result.config.$schema, "https://example.com/user-schema.json",
    "user $schema must win");
  assert.equal(result.config.model, "anthropic/claude-sonnet");
  assert.deepEqual(result.config.mcp["my-server"].command, ["my-mcp"]);
  assert.equal(result.config.mcp["arka-tools"].type, "local");
});

test("a user-modified arka-tools entry is NEVER overwritten (idempotent)", () => {
  const user = JSON.stringify({
    mcp: { "arka-tools": { type: "local", command: ["custom"], enabled: false } },
  });
  const result = mergeOpencodeConfig(user, FRAGMENT);
  assert.deepEqual(result.config.mcp["arka-tools"],
    { type: "local", command: ["custom"], enabled: false },
    "user's arka-tools must win");
  // Second pass over our own output: nothing left to change.
  const again = mergeOpencodeConfig(
    JSON.stringify(mergeOpencodeConfig("", FRAGMENT).config), FRAGMENT);
  assert.equal(again.changed, false, "merge must be idempotent");
});

test("corrupt inputs are never clobbered — null means hands off", () => {
  assert.equal(mergeOpencodeConfig("{broken", FRAGMENT), null);
  assert.equal(mergeOpencodeConfig('["array"]', FRAGMENT), null);
  assert.equal(mergeOpencodeConfig('"string"', FRAGMENT), null);
  assert.equal(mergeOpencodeConfig("{}", "{broken"), null);
});

// ── Part 3: adapter deployment (real bundle, temp configDir) ───────────

function deployToTemp(preexistingSettings = null) {
  const dir = mkdtempSync(join(tmpdir(), "arka-opencode-"));
  const config = {
    id: "opencode",
    name: "OpenCode",
    configDir: dir,
    skillsDir: join(dir, "commands"),
    settingsFile: join(dir, "opencode.json"),
  };
  if (preexistingSettings !== null) {
    writeFileSync(config.settingsFile, preexistingSettings);
  }
  adapter.configureHooks(config);
  return { dir, config };
}

test("adapter deploys AGENTS.md + every bundled agent and command file", () => {
  const { dir } = deployToTemp();
  try {
    assert.ok(existsSync(join(dir, "AGENTS.md")));
    assert.match(readFileSync(join(dir, "AGENTS.md"), "utf8"), /ArkaOS/);
    const bundledAgents = listBundleFiles("opencode", "agents");
    const bundledCommands = listBundleFiles("opencode", "commands");
    assert.ok(bundledAgents.length > 0, "committed bundle must carry agents");
    assert.ok(bundledCommands.length > 0, "committed bundle must carry commands");
    assert.deepEqual(readdirSync(join(dir, "agents")).sort(), bundledAgents.sort());
    assert.deepEqual(readdirSync(join(dir, "commands")).sort(), bundledCommands.sort());
    // Deployed opencode.json carries the MCP registration.
    const settings = JSON.parse(readFileSync(join(dir, "opencode.json"), "utf8"));
    assert.equal(settings.mcp["arka-tools"].type, "local");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("adapter preserves an existing user opencode.json on redeploy", () => {
  const user = JSON.stringify({
    model: "anthropic/claude-sonnet",
    mcp: { "arka-tools": { type: "local", command: ["custom"], enabled: false } },
  });
  const { dir } = deployToTemp(user);
  try {
    const settings = JSON.parse(readFileSync(join(dir, "opencode.json"), "utf8"));
    assert.equal(settings.model, "anthropic/claude-sonnet");
    assert.deepEqual(settings.mcp["arka-tools"].command, ["custom"],
      "user's arka-tools must survive the adapter");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("adapter leaves a corrupt user opencode.json byte-identical", () => {
  const corrupt = "{ definitely not json";
  const { dir } = deployToTemp(corrupt);
  try {
    assert.equal(readFileSync(join(dir, "opencode.json"), "utf8"), corrupt,
      "corrupt config must never be clobbered");
    // The rest of the deployment still happened.
    assert.ok(existsSync(join(dir, "AGENTS.md")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
