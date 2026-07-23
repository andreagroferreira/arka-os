// Foundation PR-4 — profile-aware doctor.
//
// Checks may declare `minProfile`; below-profile machines get an
// informational skip instead of a misleading warn (an essential machine
// without Ollama is healthy). The skip DECISION is pure
// (checkSkipReason) so it is tested directly against the real checks
// array — no doctor() run, no process.exit risk, no real probes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import {
  checks,
  checkSkipReason,
  currentInstallProfile,
} from "../../installer/doctor.js";
import { profileIncludes } from "../../installer/profile.js";

const byName = Object.fromEntries(checks.map((c) => [c.name, c]));

const PROFILE_CHECKS = [
  "install-profile",
  "litellm-proxy",
  "whisper",
  "ollama-execution-model",
];

test("all four install-profile checks are registered and warn-only", () => {
  for (const name of PROFILE_CHECKS) {
    assert.ok(byName[name], `missing doctor check: ${name}`);
    assert.equal(byName[name].severity, "warn", `${name} must be warn`);
  }
});

test("minProfile mapping matches the campaign spec", () => {
  assert.equal(byName["ollama"].minProfile, "local-ai");
  assert.equal(byName["ollama-execution-model"].minProfile, "local-ai");
  assert.equal(byName["ffmpeg"].minProfile, "complete");
  assert.equal(byName["litellm-proxy"].minProfile, "complete");
  assert.equal(byName["whisper"].minProfile, "complete");
  assert.equal(byName["install-profile"].minProfile, undefined,
    "install-profile applies to every machine");
});

test("essential machines skip ollama; local-ai machines evaluate it", () => {
  assert.equal(
    checkSkipReason(byName["ollama"], "essential"),
    "not in essential profile",
  );
  assert.equal(
    checkSkipReason(byName["ollama"], "complete"),
    "not in complete profile",
  );
  assert.equal(checkSkipReason(byName["ollama"], "local-ai"), null);
});

test("complete unlocks ffmpeg/litellm/whisper; essential skips them", () => {
  for (const name of ["ffmpeg", "litellm-proxy", "whisper"]) {
    assert.equal(
      checkSkipReason(byName[name], "essential"),
      "not in essential profile",
      name,
    );
    assert.equal(checkSkipReason(byName[name], "complete"), null, name);
    assert.equal(checkSkipReason(byName[name], "local-ai"), null, name);
  }
});

test("checks without minProfile never skip, on any profile", () => {
  for (const check of checks) {
    if (check.minProfile) continue;
    for (const profile of ["essential", "complete", "local-ai"]) {
      assert.equal(checkSkipReason(check, profile), null, check.name);
    }
  }
});

test("skip decision is consistent with profileIncludes", () => {
  for (const check of checks) {
    if (!check.minProfile) continue;
    for (const profile of ["essential", "complete", "local-ai"]) {
      const skipped = checkSkipReason(check, profile) !== null;
      assert.equal(skipped, !profileIncludes(profile, check.minProfile),
        `${check.name} @ ${profile}`);
    }
  }
});

test("install-profile check runs without throwing and returns boolean", () => {
  assert.equal(typeof byName["install-profile"].check(), "boolean");
  assert.equal(typeof byName["install-profile"].fix(), "string");
});

test("currentInstallProfile reads profile.json and degrades to essential", () => {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-doctor-profile-"));
  try {
    const path = join(dir, "profile.json");
    assert.equal(currentInstallProfile(path), "essential", "missing file");
    writeFileSync(path, JSON.stringify({ language: "en", role: "developer" }));
    assert.equal(currentInstallProfile(path), "essential", "pre-PR-3 profile");
    writeFileSync(path, JSON.stringify({ installProfile: "local-ai" }));
    assert.equal(currentInstallProfile(path), "local-ai");
    writeFileSync(path, JSON.stringify({ installProfile: "yolo" }));
    assert.equal(currentInstallProfile(path), "essential", "invalid value");
    writeFileSync(path, "{broken");
    assert.equal(currentInstallProfile(path), "essential", "corrupt json");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
