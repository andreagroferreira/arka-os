// Tests for installer/update.js:seedGlobalConfigOnUpdate — the `npx arkaos
// update` counterpart to installer/index.js's fresh-install call to
// seedArkaosConfig (index.js:329-330).
//
// Gap this closes (PR1+PR2, JEV Decisions Layer campaign; the decisions seed
// was reduced to enabled/transport/redactClients in PR5, spec D3): before this change,
// `seedArkaosConfig` was only ever invoked from the install() flow. An
// operator who only ever ran `npx arkaos update` on an existing install
// never had new template keys (hooks.hardEnforcement, decisions.*, ...)
// seeded into ~/.arkaos/config.json — the section simply never appeared,
// no matter how many times `update` ran.
//
// seedGlobalConfigOnUpdate is a thin wrapper: it calls the same
// seedArkaosConfig({ home }) as install, then logs the outcome in
// update.js's own style. The underlying idempotent contract (seed only
// what is unset, never clobber an explicit user value) is exercised in
// depth by tests/installer/config-seed.test.js; these tests only prove
// the wrapper is wired correctly end to end from an update-flow entry
// point, using a temporary HOME the same way config-seed.test.js does.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const { seedGlobalConfigOnUpdate } = await import(
  pathToFileURL(join(ROOT, "installer", "update.js"))
);

function makeTmpHome() {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-update-seed-test-"));
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

function readConfig(home) {
  return JSON.parse(readFileSync(join(home, ".arkaos", "config.json"), "utf-8"));
}

test("update flow: config.json without decisions gains only the three switches, no sites (D3)", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
    });
    await seedGlobalConfigOnUpdate(dir);
    const cfg = readConfig(dir);
    assert.deepEqual(cfg.decisions, { enabled: true, transport: "openrouter", redactClients: true },
      "update seeds the same reduced decisions block as install; sites live in Site.default_mode");
    assert.equal("sites" in cfg.decisions, false);
    // Pre-existing sections must survive the update-flow seed untouched.
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.memory.sessionMemory, true);
  } finally {
    cleanup();
  }
});

test("update flow: an operator decisions.sites.refine=\"act\" survives unchanged (D3)", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      decisions: { sites: { refine: "act", route: "off" } },
    });
    await seedGlobalConfigOnUpdate(dir);
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.deepEqual(cfg.decisions.sites, { refine: "act", route: "off" },
      "the update flow never adds, rewrites or deletes a site entry");
    assert.equal(cfg.decisions.enabled, true, "missing switches still seeded");
    assert.equal(cfg.decisions.transport, "openrouter", "missing switches still seeded");
    assert.equal(cfg.decisions.redactClients, true, "missing switches still seeded");
  } finally {
    cleanup();
  }
});

test("update flow: a full pre-5.18.0 decisions block is left byte-identical (D3)", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
      knowledge: { graphify: { enabled: true } },
      decisions: {
        enabled: true, transport: "openrouter", redactClients: true,
        hookTimeoutMs: 1500, cacheTtlSeconds: 86400,
        thresholds: { read: 0.6, write: 0.75, destructive: 0.9 },
        sites: { "topic-drift": "act", refine: "shadow", "qg-prescreen": "shadow" },
      },
    });
    const before = readFileSync(cfgPath, "utf-8");
    await seedGlobalConfigOnUpdate(dir);
    assert.equal(readFileSync(cfgPath, "utf-8"), before);
  } finally {
    cleanup();
  }
});

test("update flow: a second run is a byte-identical noop", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
    });
    await seedGlobalConfigOnUpdate(dir); // first run fills in memory.* + decisions.*
    const before = readFileSync(cfgPath, "utf-8");
    await seedGlobalConfigOnUpdate(dir); // second run — nothing left to add
    const after = readFileSync(cfgPath, "utf-8");
    assert.equal(after, before, "running the update-flow seed twice must not rewrite the file");
  } finally {
    cleanup();
  }
});

test("update flow: creates config.json from scratch when the file is absent", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    await seedGlobalConfigOnUpdate(dir);
    const cfg = readConfig(dir);
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.decisions.enabled, true);
  } finally {
    cleanup();
  }
});
