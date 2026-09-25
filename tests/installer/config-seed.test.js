// Tests for the ~/.arkaos/config.json seed/migration logic
// (PR19 v2.41.0; kbFirst added in PR-3 v4.1; decisions.* added in PR1 of
// the JEV Decisions Layer campaign; reduced to the three policy switches in
// PR5, spec D3 — decisions.sites.* is never seeded).
//
// Contract: seedArkaosConfig is idempotent. Writes each template key
// (hooks.hardEnforcement, hooks.kbFirst) to true only when the key is
// unset (file absent or key undefined). Explicit user choice (true OR
// false) is preserved unchanged. The decisions.* scalar seeds follow the
// same "only when unset" contract for arbitrary-depth, non-boolean values,
// and cover only decisions.enabled/transport/redactClients: per-site modes,
// timeouts and thresholds have their defaults in code (Site.default_mode).

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

// Import the function under test. Implementation will export it from
// installer/config-seed.js (TDD red — module does not exist yet).
const { seedArkaosConfig } = await import(pathToFileURL(join(ROOT, "installer", "config-seed.js")));

function makeTmpHome() {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-seed-test-"));
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function seedExistingConfig(home, payload) {
  const cfgPath = join(home, ".arkaos", "config.json");
  mkdirSync(dirname(cfgPath), { recursive: true });
  writeFileSync(cfgPath, JSON.stringify(payload, null, 2));
  return cfgPath;
}

test("seed creates config when file absent — hardEnforcement true", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedArkaosConfig({ home: dir });
    const cfgPath = join(dir, ".arkaos", "config.json");
    assert.ok(existsSync(cfgPath), "config.json should be created");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.hooks.kbFirst, true, "kbFirst is ON in the template (v4.1)");
  } finally {
    cleanup();
  }
});

test("seed adds key when hooks section exists but key is unset", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, { hooks: { otherKey: "preserve-me" } });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.hooks.kbFirst, true);
    assert.equal(cfg.hooks.otherKey, "preserve-me", "unknown keys must survive");
  } finally {
    cleanup();
  }
});

test("seed creates knowledge.graphify.enabled=true (nested seed)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(join(dir, ".arkaos", "config.json"), "utf-8"));
    assert.equal(cfg.knowledge.graphify.enabled, true,
      "graphify is active-once-configured by default");
  } finally {
    cleanup();
  }
});

test("seed preserves explicit knowledge.graphify.enabled=false", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      knowledge: { graphify: { enabled: false, url: "http://x/mcp" } },
    });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.knowledge.graphify.enabled, false, "user-set false must not be clobbered");
    assert.equal(cfg.knowledge.graphify.url, "http://x/mcp", "existing url must survive");
  } finally {
    cleanup();
  }
});

test("seed adds graphify.enabled on configs that predate it (added-key)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedExistingConfig(dir, { hooks: { hardEnforcement: true, kbFirst: true }, memory: { sessionMemory: true } });
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "added-key");
    const cfg = JSON.parse(readFileSync(join(dir, ".arkaos", "config.json"), "utf-8"));
    assert.equal(cfg.knowledge.graphify.enabled, true);
  } finally {
    cleanup();
  }
});

test("seed preserves explicit hardEnforcement=false", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, { hooks: { hardEnforcement: false } });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, false, "user-set false must not be clobbered");
  } finally {
    cleanup();
  }
});

test("seed preserves explicit kbFirst=false", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: false },
    });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.kbFirst, false, "user-set false must not be clobbered");
  } finally {
    cleanup();
  }
});

test("seed adds kbFirst=true on pre-v4.1 configs (hardEnforcement only)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, { hooks: { hardEnforcement: true } });
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "added-key");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.hooks.kbFirst, true);
  } finally {
    cleanup();
  }
});

test("seed is idempotent when all template keys are true", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
      knowledge: { graphify: { enabled: true } },
      decisions: { enabled: true, transport: "openrouter", redactClients: true },
    });
    const before = readFileSync(cfgPath, "utf-8");
    seedArkaosConfig({ home: dir });
    const after = readFileSync(cfgPath, "utf-8");
    // No clobber, no whitespace churn when values already correct.
    assert.equal(after, before, "no-op when already true — must not rewrite file");
  } finally {
    cleanup();
  }
});

test("seed preserves unrelated top-level keys", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: {},
      profile: { name: "test" },
      customSection: { a: 1, b: [2, 3] },
    });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.profile.name, "test");
    assert.deepEqual(cfg.customSection, { a: 1, b: [2, 3] });
  } finally {
    cleanup();
  }
});

test("seed tolerates malformed JSON without throwing", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = join(dir, ".arkaos", "config.json");
    mkdirSync(dirname(cfgPath), { recursive: true });
    writeFileSync(cfgPath, "{ this is not json at all");
    // Must not throw. Replaces with safe default on corrupt input.
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, true);
  } finally {
    cleanup();
  }
});

test("seed returns a status object describing the action taken", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const r1 = seedArkaosConfig({ home: dir });
    assert.equal(r1.action, "created");

    const r2 = seedArkaosConfig({ home: dir });
    assert.equal(r2.action, "noop", "second run should be a no-op");

    seedExistingConfig(dir, {
      hooks: { hardEnforcement: false, kbFirst: false },
      memory: { sessionMemory: false },
      knowledge: { graphify: { enabled: false } },
      decisions: { enabled: true, transport: "openrouter", redactClients: true },
    });
    const r3 = seedArkaosConfig({ home: dir });
    assert.equal(r3.action, "preserved-user-false");

    // Mixed state: one key explicitly false, the other unset — adding the
    // unset key outranks preservation in the reported action.
    seedExistingConfig(dir, { hooks: { hardEnforcement: false } });
    const r4 = seedArkaosConfig({ home: dir });
    assert.equal(r4.action, "added-key");
    const cfg = JSON.parse(readFileSync(join(dir, ".arkaos", "config.json"), "utf-8"));
    assert.equal(cfg.hooks.hardEnforcement, false, "explicit false survives the added-key write");
    assert.equal(cfg.hooks.kbFirst, true);
  } finally {
    cleanup();
  }
});

test("seed adds memory.sessionMemory to legacy hooks-only configs (F1-A2)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
    });
    const r = seedArkaosConfig({ home: dir });
    assert.equal(r.action, "added-key");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.memory.sessionMemory, true);
    assert.equal(cfg.hooks.hardEnforcement, true, "existing sections untouched");
  } finally {
    cleanup();
  }
});

test("seed preserves memory.sessionMemory=false (operator opt-out)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: false },
    });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.memory.sessionMemory, false, "explicit false is never overwritten");
  } finally {
    cleanup();
  }
});

// --- decisions.* (JEV Decisions Layer; reduced seed, PR5 spec D3) --------

const DECISIONS_SEED = { enabled: true, transport: "openrouter", redactClients: true };

// Every site mode the pre-5.18.0 seed used to write — used as a legacy
// block that must survive untouched.
const LEGACY_SITES = {
  "topic-drift": "act",
  refine: "shadow",
  route: { mode: "act", minConfidence: 0.7, timeoutMs: 1000 },
  "bash-effect": { mode: "act", timeoutMs: 1000 },
  "qg-prescreen": "shadow",
};

test("D3: a fresh config gets exactly the three decisions policy switches and no sites", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(join(dir, ".arkaos", "config.json"), "utf-8"));
    assert.deepEqual(cfg.decisions, DECISIONS_SEED,
      "decisions must hold only enabled/transport/redactClients");
    assert.equal("sites" in cfg.decisions, false,
      "decisions.sites is never seeded: Site.default_mode is the single source");
    for (const k of ["hookTimeoutMs", "cacheTtlSeconds", "thresholds"]) {
      assert.equal(k in cfg.decisions, false, `decisions.${k} has its default in code`);
    }
  } finally {
    cleanup();
  }
});

test("D3: a corrupt config is rewritten with the reduced decisions seed (no sites)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = join(dir, ".arkaos", "config.json");
    mkdirSync(dirname(cfgPath), { recursive: true });
    writeFileSync(cfgPath, "{ nope");
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "rewrote-corrupt");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.deepEqual(cfg.decisions, DECISIONS_SEED);
  } finally {
    cleanup();
  }
});

test("D3: an existing config without decisions gains the switches and no sites", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
      knowledge: { graphify: { enabled: true } },
    });
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "added-key");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.deepEqual(cfg.decisions, DECISIONS_SEED);
  } finally {
    cleanup();
  }
});

test("D3: a pre-release decisions.sites block survives byte-identical (never rewritten, never deleted)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
      knowledge: { graphify: { enabled: true } },
      decisions: {
        ...DECISIONS_SEED,
        hookTimeoutMs: 1500,
        cacheTtlSeconds: 86400,
        thresholds: { read: 0.6, write: 0.75, destructive: 0.9 },
        sites: LEGACY_SITES,
      },
    });
    const before = readFileSync(cfgPath, "utf-8");
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "noop");
    assert.equal(readFileSync(cfgPath, "utf-8"), before,
      "legacy seeded keys are the operator's now: left exactly as found");
  } finally {
    cleanup();
  }
});

test("D3: an operator sites override survives while missing switches are filled", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      decisions: { sites: { refine: "act", route: "off", "bash-effect": { timeoutMs: 800 } } },
    });
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "added-key");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.deepEqual(cfg.decisions.sites,
      { refine: "act", route: "off", "bash-effect": { timeoutMs: 800 } },
      "no site is added, removed or completed by the seed");
    assert.equal(cfg.decisions.enabled, true);
    assert.equal(cfg.decisions.transport, "openrouter");
    assert.equal(cfg.decisions.redactClients, true);
  } finally {
    cleanup();
  }
});

test("D3: explicit decisions scalars are never overwritten", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
      knowledge: { graphify: { enabled: true } },
      decisions: { enabled: false, transport: "local", redactClients: false },
    });
    const before = readFileSync(cfgPath, "utf-8");
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "noop");
    assert.equal(readFileSync(cfgPath, "utf-8"), before);
  } finally {
    cleanup();
  }
});

test("D3: explicit decisions.enabled=false survives while the other switches are filled", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, { decisions: { enabled: false } });
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "added-key");
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.deepEqual(cfg.decisions, { enabled: false, transport: "openrouter", redactClients: true });
  } finally {
    cleanup();
  }
});

test("D3: a non-object decisions value is preserved whole", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, { decisions: false });
    seedArkaosConfig({ home: dir });
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.decisions, false, "the seed never descends into a non-object value");
  } finally {
    cleanup();
  }
});

test("D3: seed run twice on a fresh install is a byte-identical noop", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedArkaosConfig({ home: dir });
    const cfgPath = join(dir, ".arkaos", "config.json");
    const before = readFileSync(cfgPath, "utf-8");
    const result = seedArkaosConfig({ home: dir });
    assert.equal(result.action, "noop");
    assert.equal(readFileSync(cfgPath, "utf-8"), before);
  } finally {
    cleanup();
  }
});
