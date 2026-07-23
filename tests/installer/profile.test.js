// Foundation PR-3 — install profiles (essential/complete/local-ai).
// Pure helpers: flag normalization and the profile.json record builder
// (previously inline in installer/index.js step 11).
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_PROFILE,
  INSTALL_PROFILES,
  PROFILE_HINTS,
  buildProfileRecord,
  normalizeProfileFlag,
  profileIncludes,
} from "../../installer/profile.js";

test("INSTALL_PROFILES is the canonical three-tier ladder", () => {
  assert.deepEqual(INSTALL_PROFILES, ["essential", "complete", "local-ai"]);
  assert.equal(DEFAULT_PROFILE, "essential");
  for (const p of INSTALL_PROFILES) {
    assert.ok(PROFILE_HINTS[p], `profile ${p} must have a wizard hint`);
  }
});

test("normalizeProfileFlag accepts canonical values", () => {
  assert.equal(normalizeProfileFlag("essential"), "essential");
  assert.equal(normalizeProfileFlag("complete"), "complete");
  assert.equal(normalizeProfileFlag("local-ai"), "local-ai");
});

test("normalizeProfileFlag is forgiving on case and whitespace", () => {
  assert.equal(normalizeProfileFlag("  Essential "), "essential");
  assert.equal(normalizeProfileFlag("LOCAL-AI"), "local-ai");
});

test("normalizeProfileFlag rejects invalid or empty input with null", () => {
  assert.equal(normalizeProfileFlag("yolo"), null);
  assert.equal(normalizeProfileFlag(""), null);
  assert.equal(normalizeProfileFlag("   "), null);
  assert.equal(normalizeProfileFlag(undefined), null);
  assert.equal(normalizeProfileFlag(null), null);
  assert.equal(normalizeProfileFlag(42), null);
});

const USER_CONFIG = {
  language: "pt",
  market: "Portugal",
  role: "developer",
  company: "WizardingCode",
  projectsDir: "/tmp/projects",
  vaultPath: "/tmp/vault",
};

test("buildProfileRecord defaults installProfile to essential", () => {
  const record = buildProfileRecord(USER_CONFIG, null);
  assert.equal(record.version, "2");
  assert.equal(record.language, "pt");
  assert.equal(record.role, "developer");
  assert.equal(record.installProfile, "essential");
  assert.ok(!Number.isNaN(Date.parse(record.created)), "created is a valid date");
  assert.ok(!Number.isNaN(Date.parse(record.updated)), "updated is a valid date");
});

test("buildProfileRecord persists the user's chosen profile", () => {
  const record = buildProfileRecord(
    { ...USER_CONFIG, installProfile: "local-ai" },
    null,
  );
  assert.equal(record.installProfile, "local-ai");
});

test("buildProfileRecord preserves the previous profile on upgrade", () => {
  const previous = { installProfile: "complete", created: "2026-01-01T00:00:00.000Z" };
  const record = buildProfileRecord(USER_CONFIG, previous);
  assert.equal(record.installProfile, "complete",
    "an upgrade without an explicit choice must not downgrade the profile");
  assert.equal(record.created, "2026-01-01T00:00:00.000Z",
    "created must survive upgrades");
  assert.notEqual(record.updated, record.created);
});

test("buildProfileRecord: explicit user choice beats the previous record", () => {
  const previous = { installProfile: "complete" };
  const record = buildProfileRecord(
    { ...USER_CONFIG, installProfile: "essential" },
    previous,
  );
  assert.equal(record.installProfile, "essential");
});

test("buildProfileRecord ignores invalid profile values at every level", () => {
  assert.equal(
    buildProfileRecord({ ...USER_CONFIG, installProfile: "yolo" }, null).installProfile,
    "essential",
  );
  assert.equal(
    buildProfileRecord(USER_CONFIG, { installProfile: "yolo" }).installProfile,
    "essential",
  );
  assert.equal(
    buildProfileRecord({ ...USER_CONFIG, installProfile: "yolo" }, { installProfile: "complete" })
      .installProfile,
    "complete",
    "invalid user value falls through to the valid previous one",
  );
});

test("buildProfileRecord tolerates a corrupt previous record", () => {
  for (const previous of [null, undefined, "not-an-object", 42]) {
    const record = buildProfileRecord(USER_CONFIG, previous);
    assert.equal(record.installProfile, "essential");
    assert.ok(record.created);
  }
});

// ── profileIncludes — the linear ladder (Foundation PR-4) ────────────────

test("profileIncludes follows the ladder essential ⊂ complete ⊂ local-ai", () => {
  assert.equal(profileIncludes("essential", "essential"), true);
  assert.equal(profileIncludes("essential", "complete"), false);
  assert.equal(profileIncludes("essential", "local-ai"), false);
  assert.equal(profileIncludes("complete", "essential"), true);
  assert.equal(profileIncludes("complete", "complete"), true);
  assert.equal(profileIncludes("complete", "local-ai"), false);
  assert.equal(profileIncludes("local-ai", "essential"), true);
  assert.equal(profileIncludes("local-ai", "local-ai"), true);
});

test("profileIncludes degrades invalid values to the default profile", () => {
  assert.equal(profileIncludes("yolo", "essential"), true);
  assert.equal(profileIncludes("yolo", "complete"), false, "invalid current = essential");
  assert.equal(profileIncludes("local-ai", "yolo"), true, "invalid required = essential");
  assert.equal(profileIncludes(undefined, "essential"), true);
});
