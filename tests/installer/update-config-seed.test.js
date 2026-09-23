// Tests for installer/update.js:seedGlobalConfigOnUpdate — the `npx arkaos
// update` counterpart to installer/index.js's fresh-install call to
// seedArkaosConfig (index.js:329-330).
//
// Gap this closes (PR1+PR2, JEV Decisions Layer campaign): before this change,
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

test("update flow: config.json without decisions gains the full section", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    seedExistingConfig(dir, {
      hooks: { hardEnforcement: true, kbFirst: true },
      memory: { sessionMemory: true },
    });
    await seedGlobalConfigOnUpdate(dir);
    const cfg = readConfig(dir);
    assert.equal(cfg.decisions.enabled, true);
    assert.equal(cfg.decisions.transport, "openrouter");
    assert.equal(cfg.decisions.redactClients, true);
    assert.equal(cfg.decisions.hookTimeoutMs, 1500);
    assert.equal(cfg.decisions.cacheTtlSeconds, 86400);
    assert.deepEqual(cfg.decisions.thresholds, { read: 0.6, write: 0.75, destructive: 0.9 });
    assert.equal(cfg.decisions.sites["topic-drift"], "act");
    assert.equal(cfg.decisions.sites.refine, "shadow");
    assert.equal(cfg.decisions.sites["creation-intent"], "act");
    assert.deepEqual(cfg.decisions.sites.route, { mode: "act", minConfidence: 0.7, timeoutMs: 1000 });
    assert.deepEqual(cfg.decisions.sites["bash-effect"], { mode: "act", timeoutMs: 1000 });
    assert.equal(cfg.decisions.sites["forge-departments"], "shadow");
    assert.equal(cfg.decisions.sites["forge-complexity"], "shadow");
    assert.equal(cfg.decisions.sites["skill-hints"], "act");
    assert.equal(cfg.decisions.sites["dispatch-role"], "act");
    assert.equal(cfg.decisions.sites["subagent-discipline"], "act");
    // Pre-existing sections must survive the update-flow seed untouched.
    assert.equal(cfg.hooks.hardEnforcement, true);
    assert.equal(cfg.memory.sessionMemory, true);
  } finally {
    cleanup();
  }
});

test("update flow: user decisions.sites.route=\"off\" survives, rest is filled in", async () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const cfgPath = seedExistingConfig(dir, {
      decisions: { sites: { route: "off" } },
    });
    await seedGlobalConfigOnUpdate(dir);
    const cfg = JSON.parse(readFileSync(cfgPath, "utf-8"));
    assert.equal(cfg.decisions.sites.route, "off",
      "the update flow must never overwrite an explicit user site mode");
    assert.equal(cfg.decisions.sites["topic-drift"], "act", "sibling sites still seeded");
    assert.equal(cfg.decisions.enabled, true, "other decisions scalars still seeded");
    assert.equal(cfg.decisions.transport, "openrouter", "other decisions scalars still seeded");
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
