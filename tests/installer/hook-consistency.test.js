import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function extractStringArray(source, varName) {
  const re = new RegExp(
    `(?:const|let|var)\\s+${varName}\\s*=\\s*\\[([\\s\\S]*?)\\]`,
    "m"
  );
  const m = source.match(re);
  if (!m) throw new Error(`Could not locate array ${varName}`);
  return [...m[1].matchAll(/["']([^"']+)["']/g)].map((x) => x[1]);
}

function extractRegisteredHooks(adapterSource) {
  const names = [];
  for (const m of adapterSource.matchAll(
    /hookEntry\s*\(\s*hooksDir\s*,\s*["']([^"']+)["']/g
  )) {
    names.push(m[1]);
  }
  return names;
}

const adapterSrc = readFileSync(
  join(ROOT, "installer/adapters/claude-code.js"),
  "utf-8"
);
const installerSrc = readFileSync(
  join(ROOT, "installer/index.js"),
  "utf-8"
);
const doctorSrc = readFileSync(
  join(ROOT, "installer/doctor.js"),
  "utf-8"
);

const registered = extractRegisteredHooks(adapterSrc);
const copied = extractStringArray(installerSrc, "hookNames");
const doctorRequired = extractStringArray(doctorSrc, "required");

test("adapter registers at least one hook", () => {
  assert.ok(registered.length > 0, "no hooks found in adapter");
});

test("every hook registered by the adapter is copied by the installer", () => {
  const missing = registered.filter((h) => !copied.includes(h));
  assert.deepEqual(
    missing,
    [],
    `installer/index.js hookNames is missing: ${missing.join(", ")} — add them to the hookNames array or the hook will never reach ~/.arkaos/config/hooks/ (see v2.20.0 regression)`
  );
});

test("every hook copied by the installer is validated by the doctor", () => {
  const missing = copied.filter((h) => !doctorRequired.includes(h));
  assert.deepEqual(
    missing,
    [],
    `installer/doctor.js "required" list is missing: ${missing.join(", ")} — drift between installer and doctor will hide future breakage`
  );
});

test("every hook copied has a source .sh file in config/hooks/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const missing = copied.filter(
    (h) => !existsSync(join(hooksDir, `${h}.sh`))
  );
  assert.deepEqual(
    missing,
    [],
    `config/hooks/ is missing .sh files for: ${missing.join(", ")}`
  );
});

test("every hook copied has a source .ps1 file in config/hooks/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const missing = copied.filter(
    (h) => !existsSync(join(hooksDir, `${h}.ps1`))
  );
  assert.deepEqual(
    missing,
    [],
    `config/hooks/ is missing .ps1 files for: ${missing.join(", ")}`
  );
});

test("_lib/ deps referenced by hooks exist in config/hooks/_lib/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const libDir = join(hooksDir, "_lib");
  const referenced = new Set();
  for (const h of copied) {
    const sh = join(hooksDir, `${h}.sh`);
    if (!existsSync(sh)) continue;
    const src = readFileSync(sh, "utf-8");
    for (const m of src.matchAll(/_lib\/([a-zA-Z0-9_-]+\.sh)/g)) {
      referenced.add(m[1]);
    }
  }
  const present = existsSync(libDir)
    ? new Set(readdirSync(libDir).filter((f) => f.endsWith(".sh")))
    : new Set();
  const missing = [...referenced].filter((f) => !present.has(f));
  assert.deepEqual(
    missing,
    [],
    `config/hooks/_lib/ is missing files referenced by hooks: ${missing.join(", ")}`
  );
});

test("VERSION file matches package.json version", () => {
  const pkg = JSON.parse(
    readFileSync(join(ROOT, "package.json"), "utf-8")
  );
  const versionFile = readFileSync(join(ROOT, "VERSION"), "utf-8").trim();
  assert.equal(
    pkg.version,
    versionFile,
    "VERSION and package.json version must match before publish"
  );
});

// ── F2-6 fast-path lockstep ─────────────────────────────────────────────

const hookLibSrc = readFileSync(join(ROOT, "installer/hook-lib.js"), "utf-8");
const hookAssets = extractStringArray(hookLibSrc, "HOOK_ASSETS");

test("every fast-path asset in HOOK_ASSETS exists in config/hooks/", () => {
  const missing = hookAssets.filter(
    (a) => !existsSync(join(ROOT, "config", "hooks", a))
  );
  assert.deepEqual(missing, [],
    `hook-lib.js HOOK_ASSETS references missing sources: ${missing.join(", ")}`);
});

test("every FASTPATH_HOOK the adapter can register has its .cjs in HOOK_ASSETS and its .sh delegation target in hookNames", () => {
  const m = adapterSrc.match(/FASTPATH_HOOKS\s*=\s*new Set\(\[([\s\S]*?)\]\)/);
  assert.ok(m, "FASTPATH_HOOKS not found in adapter");
  const fastpath = [...m[1].matchAll(/["']([^"']+)["']/g)].map((x) => x[1]);
  assert.ok(fastpath.length > 0);
  for (const name of fastpath) {
    assert.ok(hookAssets.includes(`${name}.cjs`),
      `${name}.cjs must be in hook-lib.js HOOK_ASSETS or it never deploys`);
    assert.ok(copied.includes(name),
      `${name}.sh must stay in hookNames — it is the delegation target`);
  }
});

test("gate-manifest.json is deployed whenever any shim is (same asset list)", () => {
  assert.ok(hookAssets.includes("gate-manifest.json"),
    "shims without a sibling manifest delegate everything — deploy it");
});

// ─── PR-A3: the UserPromptSubmit timeout is one number everywhere ────────
// The 10s -> 20s raise missed install.sh's three jq branches once; an
// install landing on any of them got exactly the ceiling the change
// removed. Locked across all four surfaces that write it — the adapter,
// install.sh's three jq branches and arka-doctor --fix, all pinned to
// config/settings-template.json.

// A failing tool throws inside the runtime and fires PostToolUseFailure,
// never PostToolUse (proven live against the 2.1.220 binary). A surface
// that registers only PostToolUse silently loses every failed-command
// turn — the gotchas pipeline's primary material.
test("PostToolUseFailure is registered wherever PostToolUse is", () => {
  const template = JSON.parse(
    readFileSync(join(ROOT, "config/settings-template.json"), "utf-8")
  );
  assert.ok(template.hooks.PostToolUseFailure,
    "settings-template must register PostToolUseFailure");
  assert.deepEqual(
    template.hooks.PostToolUseFailure, template.hooks.PostToolUse,
    "failure event must run the same hook with the same timeout");

  const templateTimeout =
    template.hooks.PostToolUseFailure[0].hooks[0].timeout;

  // Presence alone is not enough on the adapter — it is the
  // highest-traffic writer (install and update both route through
  // configureHooks), so its timeout must be pinned too.
  const adapterFailure = adapterSrc.match(
    /settings\.hooks\.PostToolUseFailure\s*=[\s\S]{0,160}?hookEntry\(hooksDir, "post-tool-use", (\d+)\)/
  );
  assert.ok(adapterFailure, "adapter must register PostToolUseFailure");
  assert.equal(Number(adapterFailure[1]), templateTimeout,
    "adapter registration must agree with the template timeout");

  // Same pin for the non-failure PostToolUse on both writers. The
  // doctor pattern keeps the closing quote — a bare PostToolUse
  // substring would also match PostToolUseFailure.
  const adapterPost = adapterSrc.match(
    /settings\.hooks\.PostToolUse\s*=[\s\S]{0,160}?hookEntry\(hooksDir, "post-tool-use", (\d+)\)/
  );
  assert.ok(adapterPost, "adapter must register PostToolUse");
  assert.equal(Number(adapterPost[1]), templateTimeout,
    "adapter PostToolUse timeout must agree with the template");

  const installSrc = readFileSync(join(ROOT, "install.sh"), "utf-8");
  const installTimeouts = [
    ...installSrc.matchAll(/PostToolUseFailure[^\n]*?"timeout":(\d+)/g),
  ].map((m) => Number(m[1]));
  assert.ok(installTimeouts.length >= 3,
    "install.sh must register PostToolUseFailure in its three jq branches");
  for (const t of installTimeouts) {
    assert.equal(t, templateTimeout,
      "every install.sh registration must agree with the template timeout");
  }

  // bin/arka-doctor --fix replaces `.hooks` wholesale (jq `.hooks =
  // $hooks`) whenever its hooks check fails, so whatever HOOKS_JSON
  // omits is missing from every machine the doctor repairs.
  const doctorSrc = readFileSync(join(ROOT, "bin", "arka-doctor"), "utf-8");
  const doctorTimeouts = [
    ...doctorSrc.matchAll(/PostToolUseFailure[^\n]*?"timeout":(\d+)/g),
  ].map((m) => Number(m[1]));
  assert.ok(doctorTimeouts.length >= 1,
    "arka-doctor --fix must register PostToolUseFailure");
  for (const t of doctorTimeouts) {
    assert.equal(t, templateTimeout,
      "arka-doctor's registration must agree with the template timeout");
  }

  const doctorPost = [
    ...doctorSrc.matchAll(/"PostToolUse":[^\n]*?"timeout":(\d+)/g),
  ].map((m) => Number(m[1]));
  assert.ok(doctorPost.length >= 1,
    "arka-doctor --fix must register PostToolUse");
  for (const t of doctorPost) {
    assert.equal(t, templateTimeout,
      "arka-doctor's PostToolUse timeout must agree with the template");
  }
});

test("UserPromptSubmit timeout is identical across template, adapter and install.sh", () => {
  const template = JSON.parse(
    readFileSync(join(ROOT, "config/settings-template.json"), "utf-8")
  );
  const templateTimeout =
    template.hooks.UserPromptSubmit[0].hooks[0].timeout;

  const adapterMatch = adapterSrc.match(
    /hookEntry\(hooksDir, "user-prompt-submit", (\d+)\)/
  );
  assert.ok(adapterMatch, "adapter must register user-prompt-submit");
  const adapterTimeout = Number(adapterMatch[1]);

  const installSrc = readFileSync(join(ROOT, "install.sh"), "utf-8");
  const installTimeouts = [
    ...installSrc.matchAll(
      /UserPromptSubmit[^\n]*?"timeout":(\d+)/g
    ),
  ].map((m) => Number(m[1]));
  assert.ok(installTimeouts.length >= 3,
    "install.sh must declare the UPS timeout in its three jq branches");

  // arka-doctor --fix is a fourth surface writing this timeout — it
  // shipped 10, the pre-PR-A3 value, until the PostToolUseFailure
  // wiring swept it, so every machine it repaired landed on the
  // ceiling PR-A3 removed.
  const doctorSrc = readFileSync(join(ROOT, "bin", "arka-doctor"), "utf-8");
  const doctorTimeouts = [
    ...doctorSrc.matchAll(/UserPromptSubmit[^\n]*?"timeout":(\d+)/g),
  ].map((m) => Number(m[1]));
  assert.ok(doctorTimeouts.length >= 1,
    "arka-doctor --fix must declare the UPS timeout");

  for (const t of [adapterTimeout, ...installTimeouts, ...doctorTimeouts]) {
    assert.equal(t, templateTimeout,
      "every surface must agree with config/settings-template.json");
  }
  assert.equal(templateTimeout, 20, "PR-A3 ceiling");
});
