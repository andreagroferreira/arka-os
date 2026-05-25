// Tests for the autoMode.hard_deny seeder (PR45 v2.64.0).
//
// Operates on a temp HOME so the operator's real ~/.claude/settings.json
// is never touched.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  DEFAULT_HARD_DENY_RULES,
  seedAutoModeHardDeny,
} = await import(join(ROOT, "installer", "hard-deny.js"));


function makeTmpHome({ settings, userExtensions } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-hard-deny-test-"));
  if (settings !== undefined) {
    const path = join(dir, ".claude", "settings.json");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(settings, null, 2));
  }
  if (userExtensions !== undefined) {
    const path = join(dir, ".arkaos", "hard-deny.json");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(userExtensions, null, 2));
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


test("no-op when runtime is not Claude Code", () => {
  const home = makeTmpHome({ settings: { hooks: {} } });
  try {
    const result = seedAutoModeHardDeny({ runtime: "codex", home: home.dir });
    assert.equal(result.skipped, "runtime-not-claude-code");
  } finally {
    home.cleanup();
  }
});

test("no-op when ~/.claude/settings.json does not exist", () => {
  const home = makeTmpHome();
  try {
    const result = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    assert.equal(result.skipped, "claude-settings-not-found");
  } finally {
    home.cleanup();
  }
});


// ─── Seeding on empty autoMode ──────────────────────────────────────────


test("creates autoMode.hard_deny with defaults on empty settings", () => {
  const home = makeTmpHome({ settings: { hooks: {} } });
  try {
    const result = seedAutoModeHardDeny({
      runtime: "claude-code", home: home.dir,
    });
    assert.equal(result.action, "created");
    const settings = loadSettings(home.settingsPath);
    assert.ok(Array.isArray(settings.autoMode.hard_deny));
    assert.ok(settings.autoMode.hard_deny.length >= DEFAULT_HARD_DENY_RULES.length);
    // Sanity: known high-value entries are present
    assert.ok(settings.autoMode.hard_deny.includes("Bash(git push --force*)"));
    assert.ok(settings.autoMode.hard_deny.includes("Read(~/.ssh/*)"));
  } finally {
    home.cleanup();
  }
});

test("preserves unrelated settings.json keys", () => {
  const original = {
    env: { FOO: "bar" },
    hooks: { SessionStart: [{ hooks: [{ type: "command", command: "x" }] }] },
    custom: { keep: "this" },
  };
  const home = makeTmpHome({ settings: original });
  try {
    seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    const settings = loadSettings(home.settingsPath);
    assert.deepEqual(settings.env, { FOO: "bar" });
    assert.deepEqual(settings.hooks, original.hooks);
    assert.deepEqual(settings.custom, { keep: "this" });
  } finally {
    home.cleanup();
  }
});


// ─── Idempotency ────────────────────────────────────────────────────────


test("is idempotent on repeat runs", () => {
  const home = makeTmpHome({ settings: { hooks: {} } });
  try {
    const r1 = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    assert.equal(r1.action, "created");
    const r2 = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    assert.equal(r2.action, "noop");
    const r3 = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    assert.equal(r3.action, "noop");
  } finally {
    home.cleanup();
  }
});


// ─── Operator-extension merge ───────────────────────────────────────────


test("merges ~/.arkaos/hard-deny.json operator entries", () => {
  const home = makeTmpHome({
    settings: { hooks: {} },
    userExtensions: {
      hard_deny: ["Bash(my-team-secret-cmd*)", "Read(~/.my-team-secrets/*)"],
    },
  });
  try {
    const result = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    const settings = loadSettings(home.settingsPath);
    assert.ok(settings.autoMode.hard_deny.includes("Bash(my-team-secret-cmd*)"));
    assert.ok(settings.autoMode.hard_deny.includes("Bash(git push --force*)"));
  } finally {
    home.cleanup();
  }
});


// ─── Preserves operator-authored autoMode rules ─────────────────────────


test("preserves operator-authored autoMode.hard_deny rules", () => {
  const home = makeTmpHome({
    settings: {
      autoMode: {
        hard_deny: ["Bash(custom-org-blocker*)"],
      },
    },
  });
  try {
    const result = seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    assert.equal(result.action, "merged");
    const settings = loadSettings(home.settingsPath);
    // Operator rule preserved
    assert.ok(settings.autoMode.hard_deny.includes("Bash(custom-org-blocker*)"));
    // Defaults added
    assert.ok(settings.autoMode.hard_deny.includes("Bash(git push --force*)"));
  } finally {
    home.cleanup();
  }
});

test("does not duplicate rules across runs", () => {
  const home = makeTmpHome({
    settings: { autoMode: { hard_deny: ["Bash(git push --force*)"] } },
  });
  try {
    seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    seedAutoModeHardDeny({ runtime: "claude-code", home: home.dir });
    const settings = loadSettings(home.settingsPath);
    const occurrences = settings.autoMode.hard_deny.filter(
      (r) => r === "Bash(git push --force*)",
    );
    assert.equal(occurrences.length, 1);
  } finally {
    home.cleanup();
  }
});


// ─── Default list shape ─────────────────────────────────────────────────


test("DEFAULT_HARD_DENY_RULES includes the critical categories", () => {
  // Spot-check each load-bearing category is represented
  const hasGitForce = DEFAULT_HARD_DENY_RULES.some((r) => r.includes("git push --force"));
  const hasSshRead = DEFAULT_HARD_DENY_RULES.some((r) => r.includes(".ssh"));
  const hasAwsCreds = DEFAULT_HARD_DENY_RULES.some((r) => r.includes(".aws/credentials"));
  const hasSudo = DEFAULT_HARD_DENY_RULES.some((r) => r.startsWith("Bash(sudo"));
  const hasRmRf = DEFAULT_HARD_DENY_RULES.some((r) => r.includes("rm -rf"));
  assert.ok(hasGitForce, "git push --force must be in defaults");
  assert.ok(hasSshRead, "~/.ssh must be in defaults");
  assert.ok(hasAwsCreds, "~/.aws/credentials must be in defaults");
  assert.ok(hasSudo, "sudo must be in defaults");
  assert.ok(hasRmRf, "rm -rf must be in defaults");
});
