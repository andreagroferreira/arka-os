// Tests for the Graphify grounding-layer installer module (PR-3 v4.1).
//
// Contract: ensureGraphify is best-effort and NEVER throws — a missing
// binary degrades to a manual-install hint, it never fails the install.
// graphifyDoctor exposes a cheap presence/version probe for doctor.js.
// The MCP registry gains an OPT-IN `graphify` stdio entry (higgsfield
// pattern: registered centrally, added per-project via apply-mcps.sh).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { ensureGraphify, graphifyDoctor } from "../../installer/graphify.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const registry = JSON.parse(
  readFileSync(join(ROOT, "mcps", "registry.json"), "utf-8"),
);


// ─── ensureGraphify ──────────────────────────────────────────────────────


test("ensureGraphify dry-run never throws and returns a status shape", () => {
  const out = ensureGraphify({ dryRun: true });
  assert.ok(out.binary, "binary status must be present");
  assert.ok(typeof out.binary.installed === "boolean");
  assert.ok(out.skillInstall, "skillInstall status must be present");
  assert.ok(typeof out.skillInstall.action === "string");
});

test("ensureGraphify dry-run performs no skill installation", () => {
  const out = ensureGraphify({ dryRun: true });
  // With the binary present the dry-run skips `graphify install`;
  // without it the skip reason is binary-missing. Either way: skipped.
  assert.equal(out.skillInstall.action, "skipped");
});

test("ensureGraphify dry-run surfaces the manual hint when binary missing", () => {
  const out = ensureGraphify({ dryRun: true });
  if (!out.binary.installed) {
    assert.match(out.binary.hint, /graphifyy/, "hint must name the PyPI package (double y)");
    assert.match(out.binary.hint, /uv tool install/, "hint must lead with uv");
  } else {
    assert.ok(out.binary.location, "installed binary must carry its location");
  }
});

test("ensureGraphify is idempotent (two dry-runs agree)", () => {
  const first = ensureGraphify({ dryRun: true });
  const second = ensureGraphify({ dryRun: true });
  assert.equal(first.binary.installed, second.binary.installed);
});


// ─── graphifyDoctor ──────────────────────────────────────────────────────


test("graphifyDoctor returns the doctor probe shape and never throws", () => {
  const status = graphifyDoctor();
  assert.ok(typeof status.installed === "boolean");
  assert.ok("version" in status);
  assert.ok("location" in status);
  if (!status.installed) {
    assert.match(status.hint, /graphifyy/);
  }
});


// ─── MCP registry entry (opt-in, higgsfield pattern) ────────────────────


test("registry defines the graphify MCP as stdio command", () => {
  const gf = registry.mcpServers.graphify;
  assert.ok(gf, "registry.json must define a `graphify` server");
  assert.equal(gf.command, "graphify");
  assert.deepEqual(gf.args, [".", "--mcp"]);
});

test("graphify MCP is opt-in and requires no env secrets", () => {
  const gf = registry.mcpServers.graphify;
  assert.equal(gf.env, undefined, "graphify is local/free — no env block");
  assert.equal(gf.required_env, undefined, "no required_env — nothing to leak");
  assert.match(gf.description, /OPT-IN/i, "description must state the opt-in contract");
  assert.match(gf.description, /apply-mcps\.sh --add graphify/);
});

test("graphify MCP is not baked into any stack profile (opt-in only)", () => {
  const profilesDir = join(ROOT, "mcps", "profiles");
  for (const file of readdirSync(profilesDir)) {
    if (!file.endsWith(".json")) continue;
    const profile = JSON.parse(readFileSync(join(profilesDir, file), "utf-8"));
    assert.ok(
      !(profile.mcps || []).includes("graphify"),
      `profile ${file} must not auto-include graphify — it is opt-in`,
    );
  }
});
