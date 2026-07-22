import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  checks,
  hooksWired,
  statuslineConfigured,
  gotchasHealthy,
  mcpRegistryHealthy,
  deployedSkillCount,
} from "../../installer/doctor.js";
import { IS_WINDOWS } from "../../installer/platform.js";

// Claude-layer checks migrated from the retired bash doctor (issue
// #358). The bash side had a bats lock on 18; the node doctor never had
// a count lock at all — this file adds one so a silently dropped or
// duplicated check fails the suite instead of shipping.

const CLAUDE_LAYER_CHECKS = [
  "claude-cli",
  "arka-skill",
  "jq",
  "statusline",
  "hooks-wired",
  "skills-deployed",
  "mcp-registry",
  "watch-media-tooling",
  "gotchas",
  "companion-plugins",
];

// 26 pre-#358 POSIX checks + 10 migrated Claude-layer + 1 autoupdate
// (Foundation PR-1); Windows appends 4.
const EXPECTED_TOTAL = 37 + (IS_WINDOWS ? 4 : 0);

const byName = Object.fromEntries(checks.map((c) => [c.name, c]));

test("doctor check count is locked", () => {
  assert.equal(
    checks.length,
    EXPECTED_TOTAL,
    `doctor has ${checks.length} checks, lock expects ${EXPECTED_TOTAL} — ` +
      "update this lock deliberately when adding/removing a check"
  );
});

test("doctor check names are unique", () => {
  const names = checks.map((c) => c.name);
  assert.equal(new Set(names).size, names.length, "duplicate check name");
});

test("all migrated Claude-layer checks are registered", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    assert.ok(byName[name], `missing doctor check: ${name}`);
  }
});

test("Claude-layer checks are warn-only (multi-runtime installs must not fail)", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    assert.equal(byName[name].severity, "warn", `${name} must be warn`);
  }
});

test("Claude-layer checks run without throwing and return boolean", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    const result = byName[name].check();
    assert.equal(typeof result, "boolean", `${name}.check() must be boolean`);
  }
});

test("Claude-layer fixes are instructions, not installers", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    const fix = byName[name].fix();
    assert.equal(typeof fix, "string");
    assert.ok(fix.length > 10, `${name}.fix() must instruct the operator`);
  }
});

// ─── hooksWired — the governance-live gap the bash doctor covered and
// the node hooks-dir check (files on disk) never did.

test("hooksWired: no settings.json means not applicable (true)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    assert.equal(hooksWired(join(dir, "settings.json")), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: settings without hooks is unwired (false)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(p, JSON.stringify({ statusLine: {} }));
    assert.equal(hooksWired(p), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: UserPromptSubmit wiring flips it to true", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(
      p,
      JSON.stringify({ hooks: { UserPromptSubmit: [{ hooks: [] }] } })
    );
    assert.equal(hooksWired(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: corrupt settings.json is unverifiable, surfaced as false", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(p, "{not json");
    assert.equal(hooksWired(p), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── statuslineConfigured

test("statuslineConfigured: command must point at an existing file", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sl-"));
  try {
    const p = join(dir, "settings.json");
    const cmd = join(dir, "statusline.sh");
    writeFileSync(p, JSON.stringify({ statusLine: { command: cmd } }));
    assert.equal(statuslineConfigured(p), false, "dangling command must fail");
    writeFileSync(cmd, "#!/bin/bash\n");
    assert.equal(statuslineConfigured(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("statuslineConfigured: no settings.json means not applicable (true)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sl-"));
  try {
    assert.equal(statuslineConfigured(join(dir, "settings.json")), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── gotchasHealthy — live v2 state (/arka evolve ingests it)

test("gotchasHealthy: missing, corrupt, non-array, and valid states", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-gt-"));
  try {
    const p = join(dir, "gotchas.json");
    assert.equal(gotchasHealthy(p), false, "missing must be false");
    writeFileSync(p, "{broken");
    assert.equal(gotchasHealthy(p), false, "corrupt must be false");
    writeFileSync(p, JSON.stringify({ not: "an array" }));
    assert.equal(gotchasHealthy(p), false, "non-array must be false");
    writeFileSync(p, "[]");
    assert.equal(gotchasHealthy(p), true, "empty array is healthy");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── mcpRegistryHealthy

test("mcpRegistryHealthy: requires parseable JSON with mcpServers", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-mr-"));
  try {
    const p = join(dir, "registry.json");
    assert.equal(mcpRegistryHealthy(p), false, "missing must be false");
    writeFileSync(p, "{broken");
    assert.equal(mcpRegistryHealthy(p), false, "corrupt must be false");
    writeFileSync(p, JSON.stringify({ mcpServers: {} }));
    assert.equal(mcpRegistryHealthy(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── deployedSkillCount

test("deployedSkillCount: counts only arka-* dirs holding a SKILL.md", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sd-"));
  try {
    assert.equal(deployedSkillCount(dir), 0);
    mkdirSync(join(dir, "arka-dev"), { recursive: true });
    assert.equal(deployedSkillCount(dir), 0, "dir without SKILL.md must not count");
    writeFileSync(join(dir, "arka-dev", "SKILL.md"), "# dev\n");
    mkdirSync(join(dir, "unrelated"), { recursive: true });
    writeFileSync(join(dir, "unrelated", "SKILL.md"), "# other\n");
    assert.equal(deployedSkillCount(dir), 1, "non arka-* dirs must not count");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
