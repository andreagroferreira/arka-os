// Tests for the worktree.baseRef seeder (PR48 v2.67.0).
//
// Operates on a temp HOME so the operator's real ~/.claude/settings.json
// is never touched.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  DEFAULT_WORKTREE_BASEREF,
  seedWorktreeBaseRef,
} = await import(join(ROOT, "installer", "worktree-baseref.js"));


function makeTmpHome({ settings } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-worktree-test-"));
  if (settings !== undefined) {
    const path = join(dir, ".claude", "settings.json");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(settings, null, 2));
  }
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
    settingsPath: join(dir, ".claude", "settings.json"),
  };
}


function loadSettings(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
}


// ─── Runtime gating ─────────────────────────────────────────────────────


test("worktree.baseRef no-op when runtime is not Claude Code", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r = seedWorktreeBaseRef({ runtime: "codex", home: home.dir });
    assert.equal(r.skipped, "runtime-not-claude-code");
  } finally {
    home.cleanup();
  }
});


test("worktree.baseRef no-op when settings.json missing", () => {
  const home = makeTmpHome();
  try {
    const r = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r.skipped, "claude-settings-not-found");
  } finally {
    home.cleanup();
  }
});


// ─── First-install behaviour ────────────────────────────────────────────


test("worktree.baseRef creates value on empty settings", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "created");
    assert.equal(r.value, DEFAULT_WORKTREE_BASEREF);
    const s = loadSettings(home.settingsPath);
    assert.equal(s.worktree.baseRef, DEFAULT_WORKTREE_BASEREF);
  } finally {
    home.cleanup();
  }
});


test("worktree.baseRef preserves unrelated settings.json keys", () => {
  const home = makeTmpHome({
    settings: { env: { FOO: "bar" }, hooks: { x: 1 } },
  });
  try {
    seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    const s = loadSettings(home.settingsPath);
    assert.deepEqual(s.env, { FOO: "bar" });
    assert.deepEqual(s.hooks, { x: 1 });
    assert.equal(s.worktree.baseRef, DEFAULT_WORKTREE_BASEREF);
  } finally {
    home.cleanup();
  }
});


// ─── Idempotency / operator override ────────────────────────────────────


test("worktree.baseRef preserves operator-authored value", () => {
  const home = makeTmpHome({
    settings: { worktree: { baseRef: "main" } },
  });
  try {
    const r = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "noop");
    assert.equal(r.value, "main");
    const s = loadSettings(home.settingsPath);
    assert.equal(s.worktree.baseRef, "main");
  } finally {
    home.cleanup();
  }
});


test("worktree.baseRef is idempotent on repeat runs", () => {
  const home = makeTmpHome({ settings: {} });
  try {
    const r1 = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r1.action, "created");
    const r2 = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r2.action, "noop");
    const r3 = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r3.action, "noop");
  } finally {
    home.cleanup();
  }
});


test("worktree.baseRef merges with existing worktree subkeys", () => {
  const home = makeTmpHome({
    settings: { worktree: { someOtherFlag: true } },
  });
  try {
    const r = seedWorktreeBaseRef({ runtime: "claude-code", home: home.dir });
    assert.equal(r.action, "merged");
    const s = loadSettings(home.settingsPath);
    assert.equal(s.worktree.baseRef, DEFAULT_WORKTREE_BASEREF);
    assert.equal(s.worktree.someOtherFlag, true);
  } finally {
    home.cleanup();
  }
});
