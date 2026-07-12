// Gate-manifest parity — Node side (F2-6). Runs the SAME corpora the
// pytest side executes against the real Python functions, here against
// the fast-path engine. Drift on either side breaks the build.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import fs from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const require = createRequire(import.meta.url);
const engine = require(
  join(repoRoot, "config", "hooks", "_lib", "fastpath", "engine.cjs")
);
const manifest = JSON.parse(
  readFileSync(join(repoRoot, "config", "hooks", "gate-manifest.json"), "utf-8")
);

function ctxWith({ config = { state: "missing", data: null }, env = {} } = {}) {
  return { homeDir: "/home/parity", env, fs, config };
}

test("manifest validates and every exported regex compiles in JS", () => {
  assert.equal(engine.validateManifest(manifest), true);
  for (const entry of manifest.bash.effect_patterns) {
    new RegExp(entry.js, entry.flags || "");
  }
  new RegExp(manifest.post.error_trigger.js, manifest.post.error_trigger.flags);
  new RegExp(manifest.session_id.js, manifest.session_id.flags || "");
});

test("bash corpus: engine replica matches every golden classification", () => {
  for (const row of manifest.corpora.bash) {
    const real = engine.bashIsEffect(row.cmd, manifest)
      ? "effect" : "discovery";
    // engine_expect (when present) marks a deliberate conservative
    // divergence: engine says effect (delegates) where Python says
    // discovery — e.g. the NBSP row behind the non-ASCII-whitespace
    // guard (QG B1).
    const expected = row.engine_expect ?? row.expect;
    assert.equal(real, expected,
      `bashIsEffect drift for ${JSON.stringify(row.cmd)}`);
    // One-sided safety invariant: the engine may over-classify EFFECT
    // (costs a delegation), never under-classify (skipped deny).
    assert.ok(!(row.expect === "effect" && real === "discovery"),
      `UNSAFE drift: Python=effect but engine=discovery for ${JSON.stringify(row.cmd)}`);
  }
});

test("engine_expect rows only ever diverge in the safe direction", () => {
  for (const row of manifest.corpora.bash) {
    if (row.engine_expect === undefined) continue;
    assert.equal(row.expect, "discovery");
    assert.equal(row.engine_expect, "effect",
      "engine_expect may only force delegation, never fast-allow");
  }
});

test("pre-tools corpus: decidePre routes every tool as the corpus expects", () => {
  const ctx = ctxWith();
  for (const { tool, expect } of manifest.corpora.pre_tools) {
    const payload = { tool_name: tool, session_id: "parity-sid", tool_input: {} };
    const decision = engine.decidePre(payload, manifest, ctx);
    const got = decision.action === "fast-allow" ? "fast_allow" : "delegate";
    assert.equal(got, expect, `decidePre drift for ${JSON.stringify(tool)}`);
  }
});

test("session-id corpus: strict validator parity (dot-only rejected)", () => {
  for (const { sid, expect } of manifest.corpora.session_ids) {
    const real = engine.safeSessionId(sid, manifest) !== null;
    assert.equal(real, expect, `safeSessionId drift for ${JSON.stringify(sid)}`);
  }
});

test("error-trigger corpus: regex parity on tool output", () => {
  const re = new RegExp(
    manifest.post.error_trigger.js, manifest.post.error_trigger.flags
  );
  for (const { output, expect } of manifest.corpora.error_trigger) {
    assert.equal(re.test(output), expect,
      `error_trigger drift for ${JSON.stringify(output)}`);
  }
});

test("pythonTruthy matches Python bool() where JS Boolean() disagrees", () => {
  assert.equal(engine.pythonTruthy([]), false);       // JS: true
  assert.equal(engine.pythonTruthy({}), false);       // JS: true
  assert.equal(engine.pythonTruthy("false"), true);   // both true
  assert.equal(engine.pythonTruthy(0), false);
  assert.equal(engine.pythonTruthy(""), false);
  assert.equal(engine.pythonTruthy(null), false);
  assert.equal(engine.pythonTruthy([0]), true);
  assert.equal(engine.pythonTruthy({ a: 1 }), true);
});

test("budgetActive mirrors cost_governor no-cap semantics", () => {
  const cases = [
    [{ state: "missing", data: null }, false],
    [{ state: "corrupt", data: null }, false],
    [{ state: "ok", data: {} }, false],
    [{ state: "ok", data: { budget: {} } }, false],
    [{ state: "ok", data: { budget: { hardCapUsd: null } } }, false],
    [{ state: "ok", data: { budget: { hardCapUsd: 0 } } }, false],
    [{ state: "ok", data: { budget: { hardCapUsd: -5 } } }, false],
    [{ state: "ok", data: { budget: { hardCapUsd: "lots" } } }, false],
    [{ state: "ok", data: { budget: { hardCapUsd: 8.5 } } }, true],
    [{ state: "ok", data: { budget: { dailyCapUsd: 1 } } }, true],
  ];
  for (const [config, expected] of cases) {
    assert.equal(engine.budgetActive(config, manifest), expected,
      `budgetActive drift for ${JSON.stringify(config)}`);
  }
});

test("hardEnforcementOn mirrors flow_enforcer flag resolution", () => {
  const on = (data) =>
    engine.hardEnforcementOn({ state: "ok", data }, manifest);
  assert.equal(engine.hardEnforcementOn(
    { state: "missing", data: null }, manifest), false);
  assert.equal(engine.hardEnforcementOn(
    { state: "corrupt", data: null }, manifest), false);
  assert.equal(on({ hooks: { hardEnforcement: true } }), true);
  assert.equal(on({ hooks: { hardEnforcement: false } }), false);
  assert.equal(on({ hooks: { hardEnforcement: "false" } }), true); // py-truthy
  assert.equal(on({ hooks: { hardEnforcement: [] } }), false);     // py bool([])
  assert.equal(on({ hooks: { hardEnforcement: {} } }), false);
  assert.equal(on({ hooks: {} }), false);
  assert.equal(on({}), false);
});

test("decidePre Bash: discovery fast-allows only with no active budget", () => {
  const payload = {
    tool_name: "Bash", session_id: "parity-sid", cwd: "/w",
    tool_input: { command: "git status" },
  };
  const noBudget = engine.decidePre(payload, manifest, ctxWith());
  assert.equal(noBudget.action, "fast-allow");
  assert.equal(noBudget.writes.length, 2); // kb_first + enforcement

  const withBudget = engine.decidePre(payload, manifest, ctxWith({
    config: { state: "ok", data: { budget: { hardCapUsd: 5 } } },
  }));
  assert.equal(withBudget.action, "delegate");

  const effect = engine.decidePre({
    ...payload, tool_input: { command: "rm -rf /tmp/x" },
  }, manifest, ctxWith());
  assert.equal(effect.action, "delegate");
});

test("decidePre fast-allow write shapes match the Python serializers", () => {
  const decision = engine.decidePre(
    { tool_name: "Read", session_id: "parity-sid", tool_input: {} },
    manifest, ctxWith()
  );
  assert.equal(decision.action, "fast-allow");
  const line = JSON.parse(decision.writes[0].line);
  assert.match(line.ts, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/);
  delete line.ts;
  assert.deepEqual(line, {
    session_id: "parity-sid", tool: "Read",
    ...manifest.telemetry.kb_first_template,
  });
  assert.ok(decision.writes[0].path.endsWith(
    manifest.home_paths.telemetry_kb_first));
});

test("decidePost delegates the stateful set, errors and stale auth", () => {
  const hardOn = { state: "ok", data: { hooks: { hardEnforcement: true } } };
  const cases = [
    [{ tool_name: "ExitPlanMode", exit_code: "0" }, ctxWith(), "delegate"],
    [{ tool_name: "Task", exit_code: "0" }, ctxWith(), "delegate"],
    [{ tool_name: "Agent", exit_code: "0" }, ctxWith(), "delegate"],
    [{ tool_name: "Read", exit_code: "1" }, ctxWith(), "delegate"],
    [{ tool_name: "Read", exit_code: "0", tool_output: "fatal: broken" },
      ctxWith(), "delegate"],
    // hard enforcement + no auth file → the confirm rescan is load-bearing
    [{ tool_name: "Read", exit_code: "0", session_id: "parity-sid" },
      ctxWith({ config: hardOn.data ? hardOn : hardOn }), "delegate"],
    // enforcement off (missing config) + benign → fast-exit
    [{ tool_name: "Read", exit_code: "0", tool_output: "ok" },
      ctxWith(), "fast-exit"],
  ];
  for (const [payload, ctx, expected] of cases) {
    const decision = engine.decidePost(payload, manifest, ctx);
    assert.equal(decision.action, expected,
      `decidePost drift for ${JSON.stringify(payload)}`);
  }
});

test("decidePost Q6: fresh auth file under hard enforcement fast-exits", () => {
  const authDir = mkdtempSync(join(tmpdir(), "arka-flow-auth-"));
  try {
    const sid = "parity-sid";
    writeFileSync(join(authDir, `${sid}.json`), JSON.stringify({
      marker_type: "routing",
      confirmed_ts: Date.now() / 1000 - 60,
      grace_count: 0, turn_grace: false,
    }));
    const ctx = ctxWith({
      config: { state: "ok", data: { hooks: { hardEnforcement: true } } },
      env: { ARKA_FLOW_AUTH_DIR: authDir },
    });
    const fresh = engine.decidePost(
      { tool_name: "Read", exit_code: "0", session_id: sid }, manifest, ctx
    );
    assert.equal(fresh.action, "fast-exit");

    // Expired auth (past TTL) → delegate so Python re-confirms.
    writeFileSync(join(authDir, `${sid}.json`), JSON.stringify({
      marker_type: "routing",
      confirmed_ts:
        Date.now() / 1000 - manifest.numbers.auth_ttl_seconds - 10,
    }));
    const stale = engine.decidePost(
      { tool_name: "Read", exit_code: "0", session_id: sid }, manifest, ctx
    );
    assert.equal(stale.action, "delegate");
  } finally {
    rmSync(authDir, { recursive: true, force: true });
  }
});

test("decidePost replicates the mcp-usage line for MCP tools", () => {
  const decision = engine.decidePost(
    { tool_name: "mcp__plugin_claude-mem_mcp-search__search",
      exit_code: "0", session_id: "parity-sid" },
    manifest, ctxWith()
  );
  assert.equal(decision.action, "fast-exit");
  assert.equal(decision.stdout, "{}");
  const line = JSON.parse(decision.writes[0].line);
  assert.equal(line.server, "plugin_claude-mem_mcp-search");
  assert.equal(line.tool, "search");
  assert.equal(line.session, "parity-sid");
  assert.deepEqual(Object.keys(line), manifest.telemetry.mcp_keys);
});

test("engine has no deny path (structural: output space is closed)", () => {
  const source = readFileSync(join(
    repoRoot, "config", "hooks", "_lib", "fastpath", "engine.cjs"), "utf-8");
  assert.ok(!/action:\s*["']deny/.test(source),
    "engine must never emit a deny action");
  assert.ok(!/permissionDecision/.test(source),
    "engine must never build a permissionDecision payload");
});

test("invalid or missing manifest delegates everything", () => {
  for (const bad of [null, {}, { schema_version: 99 }]) {
    const pre = engine.decidePre(
      { tool_name: "Read" }, bad, ctxWith());
    assert.equal(pre.action, "delegate");
    const post = engine.decidePost(
      { tool_name: "Read", exit_code: "0" }, bad, ctxWith());
    assert.equal(post.action, "delegate");
  }
});
