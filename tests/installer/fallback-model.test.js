// Tests for the fallbackModel seeder (Runtime Sync PR3).
//
// Operates on a temp HOME so the operator's real ~/.claude/settings.json
// is never touched. Same shape as worktree-baseref.test.js.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  DEFAULT_FALLBACK_MODELS,
  seedFallbackModel,
} = await import(pathToFileURL(join(ROOT, "installer", "fallback-model.js")));


function makeTmpHome({ settings, raw } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-fallback-test-"));
  const path = join(dir, ".claude", "settings.json");
  if (settings !== undefined || raw !== undefined) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, raw !== undefined ? raw : JSON.stringify(settings, null, 2));
  }
  return {
    dir,
    settingsPath: path,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}


function loadSettings(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
}


test("the seeded chain is Opus 5 then Sonnet 5", () => {
  assert.deepEqual(DEFAULT_FALLBACK_MODELS, ["claude-opus-5", "claude-sonnet-5"]);
});


// ─── Gating ─────────────────────────────────────────────────────────────


test("no-op when runtime is not Claude Code", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r = seedFallbackModel({ runtime: "codex", home: home.dir });
    assert.equal(r.skipped, "runtime-not-claude-code");
    assert.deepEqual(loadSettings(home.settingsPath), {});
  } finally {
    home.cleanup();
  }
});


test("no-op when settings.json is missing (the adapter creates it first)", () => {
  const home = makeTmpHome();
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.skipped, "claude-settings-not-found");
  } finally {
    home.cleanup();
  }
});


test("no-op when settings.json is not parseable, file untouched", () => {
  const home = makeTmpHome({ raw: "{ not json" });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.skipped, "settings-not-parseable");
    assert.equal(readFileSync(home.settingsPath, "utf-8"), "{ not json");
  } finally {
    home.cleanup();
  }
});


test("no-op when settings.json is not an object", () => {
  const home = makeTmpHome({ raw: "[1, 2]" });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.skipped, "settings-not-object");
  } finally {
    home.cleanup();
  }
});


// ─── Seed-if-absent ─────────────────────────────────────────────────────


test("seeds the chain when the key is absent and keeps the rest", () => {
  const home = makeTmpHome({ settings: { worktree: { baseRef: "head" } } });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.skipped, null);
    assert.equal(r.action, "created");
    assert.deepEqual(r.value, ["claude-opus-5", "claude-sonnet-5"]);
    const after = loadSettings(home.settingsPath);
    assert.deepEqual(after.fallbackModel, ["claude-opus-5", "claude-sonnet-5"]);
    assert.deepEqual(after.worktree, { baseRef: "head" });
    const leftovers = readdirSync(join(home.dir, ".claude")).filter((f) => f.includes(".tmp-"));
    assert.deepEqual(leftovers, [], "atomic write must leave no temp file");
  } finally {
    home.cleanup();
  }
});


test("the returned value is a copy — mutating it cannot change the default", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    r.value.push("mutated");
    assert.deepEqual(DEFAULT_FALLBACK_MODELS, ["claude-opus-5", "claude-sonnet-5"]);
  } finally {
    home.cleanup();
  }
});


test("an operator array is preserved byte for byte", () => {
  const raw = JSON.stringify({ fallbackModel: ["claude-sonnet-5"] }, null, 4) + "\n";
  const home = makeTmpHome({ raw });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "noop");
    assert.deepEqual(r.value, ["claude-sonnet-5"]);
    assert.equal(readFileSync(home.settingsPath, "utf-8"), raw);
  } finally {
    home.cleanup();
  }
});


test("the legacy string form is an operator choice too — never rewritten", () => {
  const raw = JSON.stringify({ fallbackModel: "claude-sonnet-5" }) + "\n";
  const home = makeTmpHome({ raw });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "noop");
    assert.equal(r.value, "claude-sonnet-5");
    assert.equal(readFileSync(home.settingsPath, "utf-8"), raw);
  } finally {
    home.cleanup();
  }
});


test("an explicit empty array means 'no chain' and is preserved", () => {
  const home = makeTmpHome({ settings: { fallbackModel: [] } });
  try {
    const r = seedFallbackModel({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "noop");
    assert.deepEqual(loadSettings(home.settingsPath).fallbackModel, []);
  } finally {
    home.cleanup();
  }
});


test("a custom default is honoured", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r = seedFallbackModel({
      runtime: "claude-code", home: home.dir, defaultValue: ["claude-sonnet-5"],
    });
    assert.equal(r.action, "created");
    assert.deepEqual(loadSettings(home.settingsPath).fallbackModel, ["claude-sonnet-5"]);
  } finally {
    home.cleanup();
  }
});
