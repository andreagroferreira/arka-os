import { test } from "node:test";
import assert from "node:assert/strict";
import { checks } from "../../installer/doctor.js";

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
