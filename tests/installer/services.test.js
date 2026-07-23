// Foundation PR-4 — profile → service reconciliation.
//
// HARD RULE (feedback_destructive_tests): these tests NEVER run a real
// install. Every effect (pip, brew, ollama, graphify) is a stub injected
// through the `effects` parameter; the assertions are on the DECISIONS
// (which effects were called with what), not on machine state.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import {
  loadProfilesManifest,
  ollamaListHasModel,
  parseExecutionModel,
  reconcileServices,
  resolveServicesForProfile,
} from "../../installer/services.js";
import { INSTALL_PROFILES } from "../../installer/profile.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

// ── Manifest (the real repo file is the fixture) ──────────────────────────

test("install-profiles manifest loads and validates", () => {
  const manifest = loadProfilesManifest(ROOT);
  for (const name of INSTALL_PROFILES) {
    assert.ok(manifest.profiles[name], `manifest missing profile ${name}`);
  }
  // Every referenced service resolves (validateManifest throws otherwise;
  // resolve every profile end-to-end for the extends chains too).
  for (const name of INSTALL_PROFILES) {
    const ids = resolveServicesForProfile(name, manifest);
    assert.ok(ids.length > 0, `${name} resolves to no services`);
    assert.equal(new Set(ids).size, ids.length, `${name} has duplicate service ids`);
    for (const id of ids) {
      assert.ok(manifest.services[id], `unknown service ${id}`);
    }
  }
});

test("profile ladder is a strict superset chain (essential ⊂ complete ⊂ local-ai)", () => {
  const manifest = loadProfilesManifest(ROOT);
  const essential = resolveServicesForProfile("essential", manifest);
  const complete = resolveServicesForProfile("complete", manifest);
  const localAi = resolveServicesForProfile("local-ai", manifest);
  for (const id of essential) assert.ok(complete.includes(id), `complete missing ${id}`);
  for (const id of complete) assert.ok(localAi.includes(id), `local-ai missing ${id}`);
  assert.ok(complete.length > essential.length);
  assert.ok(localAi.length > complete.length);
  // Parents come first: reconciliation repairs the base before extras.
  assert.deepEqual(complete.slice(0, essential.length), essential);
  assert.deepEqual(localAi.slice(0, complete.length), complete);
});

test("resolveServicesForProfile rejects unknown profiles and cycles", () => {
  const manifest = loadProfilesManifest(ROOT);
  assert.throws(() => resolveServicesForProfile("yolo", manifest), /unknown install profile/);

  const cyclic = {
    profiles: {
      a: { services: [], extends: "b" },
      b: { services: [], extends: "a" },
    },
    services: {},
  };
  assert.throws(() => resolveServicesForProfile("a", cyclic), /cyclic/);
});

test("loadProfilesManifest rejects dangling refs, dangling extends, and cycles", () => {
  const withManifest = (obj, fn) => {
    const dir = mkdtempSync(join(tmpdir(), "arkaos-manifest-test-"));
    try {
      mkdirSync(join(dir, "config"), { recursive: true });
      writeFileSync(
        join(dir, "config", "install-profiles.json"),
        JSON.stringify(obj),
      );
      return fn(dir);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  };

  // Dangling service ref
  withManifest(
    { profiles: { essential: { services: ["ghost"] } }, services: {} },
    (dir) => assert.throws(() => loadProfilesManifest(dir), /unknown service "ghost"/),
  );
  // Dangling extends
  withManifest(
    { profiles: { complete: { services: [], extends: "ghost" } }, services: {} },
    (dir) => assert.throws(() => loadProfilesManifest(dir), /extends unknown profile/),
  );
  // Cyclic extends
  withManifest(
    {
      profiles: {
        a: { services: [], extends: "b" },
        b: { services: [], extends: "a" },
      },
      services: {},
    },
    (dir) => assert.throws(() => loadProfilesManifest(dir), /cyclic/),
  );
  // Service without a kind
  withManifest(
    { profiles: { essential: { services: ["x"] } }, services: { x: { label: "X" } } },
    (dir) => assert.throws(() => loadProfilesManifest(dir), /has no kind/),
  );
  // Missing sections
  withManifest({ services: {} }, (dir) =>
    assert.throws(() => loadProfilesManifest(dir), /no profiles/));
});

// ── Reconcile — stubbed effects only ──────────────────────────────────────

const KNOWN_EFFECTS = [
  "pyImport", "pipInstall", "commandExists", "fileExists", "checkOllama",
  "ensureOllama", "detectManager", "installSystemPackage", "ollamaList",
  "ollamaPull", "resolveExecutionModel", "graphifyInstalled",
  "ensureGraphify", "confirm",
];
const INSTALL_EFFECTS = ["pipInstall", "installSystemPackage", "ensureOllama", "ollamaPull", "ensureGraphify"];

function stubEffects(overrides = {}) {
  const calls = [];
  const record = (name, ret) => (...args) => {
    calls.push({ name, args });
    return typeof ret === "function" ? ret(...args) : ret;
  };
  const effects = {
    pyImport: record("pyImport", true),
    pipInstall: record("pipInstall", true),
    commandExists: record("commandExists", true),
    fileExists: record("fileExists", true),
    checkOllama: record("checkOllama", { name: "ollama", installed: true, needsAction: "none" }),
    ensureOllama: record("ensureOllama", { installed: true }),
    detectManager: record("detectManager", "brew"),
    installSystemPackage: record("installSystemPackage", { installed: true }),
    ollamaList: record("ollamaList", "NAME            ID    SIZE\nkimi:cloud      abc   1GB\n"),
    ollamaPull: record("ollamaPull", true),
    resolveExecutionModel: record("resolveExecutionModel", { model: "kimi:cloud", effort: "high" }),
    graphifyInstalled: record("graphifyInstalled", true),
    ensureGraphify: record("ensureGraphify", { binary: { installed: true } }),
    confirm: async (...args) => {
      calls.push({ name: "confirm", args });
      return true;
    },
  };
  for (const [name, impl] of Object.entries(overrides)) {
    effects[name] = record(name, impl);
  }
  return { calls, effects };
}

function statuses(results) {
  return Object.fromEntries(results.map((r) => [r.id, r.status]));
}

test("everything present → all present, ZERO install effects, idempotent", async () => {
  const { calls, effects } = stubEffects();
  const run1 = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  for (const r of run1) {
    assert.equal(r.status, "present", `${r.id} expected present, got ${r.status}`);
  }
  const installCalls = calls.filter((c) => INSTALL_EFFECTS.includes(c.name));
  assert.deepEqual(installCalls, [], "present services must trigger no installs");
  // Only known effects were exercised — there is no uninstall primitive
  // in the surface at all, by construction.
  for (const c of calls) assert.ok(KNOWN_EFFECTS.includes(c.name), `unknown effect ${c.name}`);

  // Second run: identical outcome, still zero installs.
  const { calls: calls2, effects: effects2 } = stubEffects();
  const run2 = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects: effects2 });
  assert.deepEqual(statuses(run2), statuses(run1));
  assert.deepEqual(calls2.filter((c) => INSTALL_EFFECTS.includes(c.name)), []);
});

test("missing pip service → exactly one pipInstall with the manifest packages", async () => {
  const { calls, effects } = stubEffects({
    pyImport: (module) => module !== "litellm",
  });
  const results = await reconcileServices({ profile: "complete", repoRoot: ROOT, effects });
  const litellm = results.find((r) => r.id === "litellm-proxy");
  assert.equal(litellm.status, "installed");
  const pipCalls = calls.filter((c) => c.name === "pipInstall");
  assert.equal(pipCalls.length, 1);
  assert.equal(pipCalls[0].args[0], "litellm[proxy]");
});

test("pip install failure → status failed with hint, no throw, run continues", async () => {
  const { effects } = stubEffects({
    pyImport: (module) => module !== "faster_whisper",
    pipInstall: false,
  });
  const results = await reconcileServices({ profile: "complete", repoRoot: ROOT, effects });
  const whisper = results.find((r) => r.id === "whisper");
  assert.equal(whisper.status, "failed");
  assert.match(whisper.hint, /pip install/);
  // Later services still ran.
  assert.ok(results.length >= 7, "reconciliation must continue past a failure");
});

test("headless NEVER touches consent-gated services (ffmpeg, ollama)", async () => {
  const { calls, effects } = stubEffects({
    commandExists: false,             // ffmpeg missing
    checkOllama: { name: "ollama", installed: false, suggestedCommand: "brew install ollama" },
  });
  const results = await reconcileServices({
    profile: "local-ai", repoRoot: ROOT, interactive: false, effects,
  });
  const byId = statuses(results);
  assert.equal(byId.ffmpeg, "skipped");
  assert.equal(byId.ollama, "skipped");
  const ffmpeg = results.find((r) => r.id === "ffmpeg");
  assert.match(ffmpeg.hint, /brew install ffmpeg/, "hint must carry the exact command");
  const forbidden = calls.filter((c) =>
    ["installSystemPackage", "ensureOllama", "confirm"].includes(c.name));
  assert.deepEqual(forbidden, [], "headless must not install or even ask");
});

test("interactive + consent yes → system package installs; no → skip", async () => {
  const yes = stubEffects({ commandExists: false });
  const resultsYes = await reconcileServices({
    profile: "complete", repoRoot: ROOT, interactive: true, effects: yes.effects,
  });
  assert.equal(resultsYes.find((r) => r.id === "ffmpeg").status, "installed");
  assert.equal(yes.calls.filter((c) => c.name === "installSystemPackage").length, 1);
  assert.equal(yes.calls.filter((c) => c.name === "confirm").length, 1);

  const no = stubEffects({ commandExists: false });
  no.effects.confirm = async () => {
    no.calls.push({ name: "confirm", args: [] });
    return false;
  };
  const resultsNo = await reconcileServices({
    profile: "complete", repoRoot: ROOT, interactive: true, effects: no.effects,
  });
  assert.equal(resultsNo.find((r) => r.id === "ffmpeg").status, "skipped");
  assert.deepEqual(no.calls.filter((c) => c.name === "installSystemPackage"), []);
});

test("sudo-only manager → skipped with sudo hint even when interactive", async () => {
  const { calls, effects } = stubEffects({
    commandExists: false,
    detectManager: "apt",
  });
  const results = await reconcileServices({
    profile: "complete", repoRoot: ROOT, interactive: true, effects,
  });
  const ffmpeg = results.find((r) => r.id === "ffmpeg");
  assert.equal(ffmpeg.status, "skipped");
  assert.match(ffmpeg.hint, /sudo/);
  assert.deepEqual(calls.filter((c) => c.name === "installSystemPackage"), []);
});

test("execution model: missing prerequisite ollama gates the model service", async () => {
  const { calls, effects } = stubEffects({
    checkOllama: { name: "ollama", installed: false, suggestedCommand: "brew install ollama" },
  });
  const results = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  const model = results.find((r) => r.id === "ollama-execution-model");
  assert.equal(model.status, "skipped");
  assert.match(model.hint, /requires ollama/);
  assert.deepEqual(calls.filter((c) => c.name === "ollamaPull"), []);
});

test("execution model: no ollama role in models.yaml → skipped with hint", async () => {
  const { calls, effects } = stubEffects({ resolveExecutionModel: null });
  const results = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  const model = results.find((r) => r.id === "ollama-execution-model");
  assert.equal(model.status, "skipped");
  assert.match(model.hint, /models\.yaml/);
  assert.deepEqual(calls.filter((c) => c.name === "ollamaPull"), []);
});

test("execution model: missing from ollama list → exactly one pull", async () => {
  const { calls, effects } = stubEffects({
    ollamaList: "NAME    ID   SIZE\nother:latest  x  1GB\n",
  });
  const results = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  const model = results.find((r) => r.id === "ollama-execution-model");
  assert.equal(model.status, "installed");
  const pulls = calls.filter((c) => c.name === "ollamaPull");
  assert.equal(pulls.length, 1);
  assert.equal(pulls[0].args[0], "kimi:cloud");
});

test("execution model: ollama unreachable → skipped, no pull attempted", async () => {
  const { calls, effects } = stubEffects({ ollamaList: null });
  const results = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  assert.equal(results.find((r) => r.id === "ollama-execution-model").status, "skipped");
  assert.deepEqual(calls.filter((c) => c.name === "ollamaPull"), []);
});

test("unsafe model names are refused, never shelled out", async () => {
  const { calls, effects } = stubEffects({
    resolveExecutionModel: { model: "bad; rm -rf /", effort: "" },
    ollamaList: "NAME\n",
  });
  const results = await reconcileServices({ profile: "local-ai", repoRoot: ROOT, effects });
  const model = results.find((r) => r.id === "ollama-execution-model");
  assert.equal(model.status, "failed");
  assert.match(model.hint, /unsafe model name/);
  assert.deepEqual(calls.filter((c) => c.name === "ollamaPull"), []);
});

test("a throwing effect degrades that service to failed and continues", async () => {
  const { effects } = stubEffects();
  effects.graphifyInstalled = () => { throw new Error("boom"); };
  const results = await reconcileServices({ profile: "essential", repoRoot: ROOT, effects });
  const graphify = results.find((r) => r.id === "graphify");
  assert.equal(graphify.status, "failed");
  assert.match(graphify.hint, /boom/);
  assert.equal(results.length, resolveServicesForProfile("essential", loadProfilesManifest(ROOT)).length);
});

// ── parseExecutionModel — fixtures ────────────────────────────────────────

function withModelsYaml(body, fn) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-models-test-"));
  const path = join(dir, "models.yaml");
  try {
    if (body !== null) writeFileSync(path, body);
    return fn(path);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("parseExecutionModel: execution role on ollama → model + effort", () => {
  withModelsYaml(
    [
      "version: 1",
      "roles:",
      "  execution:",
      "    provider: ollama",
      "    model: kimi-k2.7-code:cloud",
      "    effort: high",
    ].join("\n"),
    (path) => {
      assert.deepEqual(parseExecutionModel(path), {
        model: "kimi-k2.7-code:cloud",
        effort: "high",
      });
    },
  );
});

test("parseExecutionModel: inline comments and quoted scalars follow YAML semantics", () => {
  // Unquoted value ends at the inline comment (canonical reader parity).
  withModelsYaml(
    [
      "roles:",
      "  execution:",
      "    provider: ollama # local runtime",
      "    model: kimi-test # pinned by operator",
      "    effort: high",
    ].join("\n"),
    (path) => {
      assert.deepEqual(parseExecutionModel(path), {
        model: "kimi-test",
        effort: "high",
      });
    },
  );
  // A "#" inside quotes is data, not a comment.
  withModelsYaml(
    [
      "roles:",
      "  execution:",
      "    provider: ollama",
      '    model: "kimi#tag"',
    ].join("\n"),
    (path) => {
      assert.equal(parseExecutionModel(path).model, "kimi#tag");
    },
  );
  // A comment-only value is an empty scalar, not the string "# note".
  withModelsYaml(
    ["roles:", "  execution:", "    provider: ollama", "    model: # note"].join("\n"),
    (path) => assert.equal(parseExecutionModel(path), null),
  );
});

test("parseExecutionModel: non-ollama provider → null", () => {
  withModelsYaml(
    ["roles:", "  execution:", "    provider: runtime", "    model: sonnet"].join("\n"),
    (path) => assert.equal(parseExecutionModel(path), null),
  );
});

test("parseExecutionModel: missing file / missing role / empty model → null", () => {
  withModelsYaml(null, (path) => assert.equal(parseExecutionModel(path), null));
  withModelsYaml("version: 1\nroles:\n  design:\n    provider: ollama\n", (path) =>
    assert.equal(parseExecutionModel(path), null));
  withModelsYaml(
    ["roles:", "  execution:", "    provider: ollama", "    model: ''"].join("\n"),
    (path) => assert.equal(parseExecutionModel(path), null),
  );
});

test("parseExecutionModel: alias slots resolve through aliases.ollama", () => {
  withModelsYaml(
    [
      "aliases:",
      "  ollama:",
      "    default: llama3:8b",
      "roles:",
      "  execution:",
      "    provider: ollama",
      "    model: default",
    ].join("\n"),
    (path) => assert.deepEqual(parseExecutionModel(path), { model: "llama3:8b", effort: "" }),
  );
});

test("parseExecutionModel: embedded ollama/<model> provider shorthand", () => {
  withModelsYaml(
    ["roles:", "  execution:", "    provider: ollama/qwen3:4b"].join("\n"),
    (path) => assert.deepEqual(parseExecutionModel(path), { model: "qwen3:4b", effort: "" }),
  );
});

test("parseExecutionModel: garbage input is tolerated, never throws", () => {
  withModelsYaml("{{{ not yaml \n\t???", (path) => assert.equal(parseExecutionModel(path), null));
});

// ── ollamaListHasModel ────────────────────────────────────────────────────

test("ollamaListHasModel matches exact tags and untagged names", () => {
  const out = "NAME            ID    SIZE\nllama3:latest   a     4GB\nkimi:cloud      b     1GB\n";
  assert.equal(ollamaListHasModel(out, "kimi:cloud"), true);
  assert.equal(ollamaListHasModel(out, "llama3"), true, "untagged matches :latest");
  assert.equal(ollamaListHasModel(out, "kimi"), true, "untagged matches any tag");
  assert.equal(ollamaListHasModel(out, "kimi:local"), false, "different tag is a miss");
  assert.equal(ollamaListHasModel(out, "mistral"), false);
});
