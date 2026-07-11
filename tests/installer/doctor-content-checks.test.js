import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { checks, hyperframesSkillsInstalled } from "../../installer/doctor.js";

// Content production prerequisites (PR-C2): all warn-only — video
// production is opt-in, the installer never fails on these and never
// installs binaries itself (detect + instruct only).

const CONTENT_CHECKS = [
  "node-22-video",
  "ffmpeg",
  "agent-reach",
  "hyperframes-skills",
  "higgsfield-api-key",
];

const byName = Object.fromEntries(checks.map((c) => [c.name, c]));

test("all five content prerequisite checks are registered", () => {
  for (const name of CONTENT_CHECKS) {
    assert.ok(byName[name], `missing doctor check: ${name}`);
  }
});

test("content prerequisite checks are warn-only (never fail the install)", () => {
  for (const name of CONTENT_CHECKS) {
    assert.equal(byName[name].severity, "warn", `${name} must be warn`);
  }
});

test("content prerequisite checks run without throwing and return boolean", () => {
  for (const name of CONTENT_CHECKS) {
    const result = byName[name].check();
    assert.equal(typeof result, "boolean", `${name}.check() must be boolean`);
  }
});

test("content prerequisite fixes are instructions, not installers", () => {
  for (const name of CONTENT_CHECKS) {
    const fix = byName[name].fix();
    assert.equal(typeof fix, "string");
    assert.ok(fix.length > 10, `${name}.fix() must instruct the operator`);
  }
});

test("node-22-video reflects the running Node version", () => {
  const major = parseInt(process.version.slice(1).split(".")[0], 10);
  assert.equal(byName["node-22-video"].check(), major >= 22);
});

test("hyperframesSkillsInstalled detects the sentinel via fixture dir", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hf-"));
  try {
    assert.equal(hyperframesSkillsInstalled(dir), false, "empty dir must be false");
    mkdirSync(join(dir, "hyperframes"), { recursive: true });
    assert.equal(hyperframesSkillsInstalled(dir), false, "dir without SKILL.md must be false");
    writeFileSync(join(dir, "hyperframes", "SKILL.md"), "# router\n");
    assert.equal(hyperframesSkillsInstalled(dir), true, "hyperframes/SKILL.md must be true");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hyperframesSkillsInstalled accepts the hyperframes-core sentinel", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hf-core-"));
  try {
    mkdirSync(join(dir, "hyperframes-core"), { recursive: true });
    writeFileSync(join(dir, "hyperframes-core", "SKILL.md"), "# core\n");
    assert.equal(hyperframesSkillsInstalled(dir), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("agent-reach fix points at the real git source, never the phantom PyPI package", () => {
  const fix = byName["agent-reach"].fix();
  assert.ok(fix.includes("github.com/Panniantong/Agent-Reach"), "must name the git source");
  assert.ok(!/\b(pipx|uv tool) install agent-reach\b/.test(fix), "must not offer the phantom PyPI install");
});

test("hyperframes-skills fix names the exact recovery command", () => {
  assert.ok(byName["hyperframes-skills"].fix().includes("/content video-setup"));
});
