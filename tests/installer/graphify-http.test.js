// Tests for the graphify HTTP knowledge-graph MCP setup (user-scope,
// config-driven endpoint).
//
// Subprocess calls (claude --version, claude mcp get/add/remove) are mocked
// via a temp PATH override so the test never touches the real CLI. The
// interactive prompts are never exercised because the test runner has no TTY
// (process.stdin.isTTY is falsy) — configureGraphifyHttp acts only on saved
// config, exactly as it does in headless/CI installs.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, chmodSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  resolveGraphifyHttpConfig,
  registerGraphifyHttpMcp,
  configureGraphifyHttp,
} = await import(join(ROOT, "installer", "graphify.js"));


// ─── Mock CLI helper ────────────────────────────────────────────────────
// `claude mcp get graphify` prints the registration state; `mcp add` and
// `mcp remove` just exit. getUrl="" simulates an unregistered server.

function makeMockClaude({ getUrl = "", addExit = 0, addStderr = "" } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-gh-claude-mock-"));
  const script = join(dir, "claude");
  const getBody = getUrl
    ? `echo "graphify:"; echo "  URL: ${getUrl}"; exit 0`
    : `exit 1`;
  const body = `#!/usr/bin/env bash
if [ "$1" = "--version" ]; then echo "claude mock 0.0.0"; exit 0; fi
if [ "$1" = "mcp" ] && [ "$2" = "get" ]; then ${getBody}; fi
if [ "$1" = "mcp" ] && [ "$2" = "remove" ]; then exit 0; fi
if [ "$1" = "mcp" ] && [ "$2" = "add" ]; then
  ${addStderr ? `echo "${addStderr.replace(/"/g, '\\"')}" >&2` : ""}
  exit ${addExit}
fi
exit 99
`;
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

function withMockedPath(mockDirs, fn) {
  const original = process.env.PATH;
  process.env.PATH = `${mockDirs.join(":")}:${original}`;
  let result;
  try {
    result = fn();
  } catch (err) {
    process.env.PATH = original;
    throw err;
  }
  if (result && typeof result.then === "function") {
    return result.finally(() => { process.env.PATH = original; });
  }
  process.env.PATH = original;
  return result;
}

function makeTmpHome({ config = null, keys = null } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-gh-home-"));
  mkdirSync(join(dir, ".arkaos"), { recursive: true });
  if (config) {
    writeFileSync(join(dir, ".arkaos", "config.json"), JSON.stringify(config, null, 2));
  }
  if (keys) {
    writeFileSync(join(dir, ".arkaos", "keys.json"), JSON.stringify(keys, null, 2));
  }
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}


// ─── resolveGraphifyHttpConfig ──────────────────────────────────────────


test("resolve: enabled defaults to true and stays not-ready without url/token", () => {
  const home = makeTmpHome();
  try {
    const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: {} });
    assert.equal(cfg.enabled, true);
    assert.equal(cfg.ready, false);
  } finally { home.cleanup(); }
});

test("resolve: url from config + token from keys → ready", () => {
  const home = makeTmpHome({
    config: { knowledge: { graphify: { enabled: true, url: "http://lab:8080/mcp" } } },
    keys: { GRAPHIFY_TOKEN: "tok-123" },
  });
  try {
    const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: {} });
    assert.equal(cfg.url, "http://lab:8080/mcp");
    assert.equal(cfg.token, "tok-123");
    assert.equal(cfg.ready, true);
  } finally { home.cleanup(); }
});

test("resolve: env GRAPHIFY_URL overrides config url", () => {
  const home = makeTmpHome({
    config: { knowledge: { graphify: { url: "http://config:8080/mcp" } } },
    keys: { GRAPHIFY_TOKEN: "t" },
  });
  try {
    const cfg = resolveGraphifyHttpConfig({
      home: home.dir, env: { GRAPHIFY_URL: "http://env:9090/mcp" },
    });
    assert.equal(cfg.url, "http://env:9090/mcp");
  } finally { home.cleanup(); }
});

test("resolve: private-range PREFIXES on a public domain are rejected", () => {
  // QG blocker (redo 4): the first validator tested the hostname STRING with
  // prefix regexes, so `10.evil.example` — a domain anyone can register —
  // passed and received the operator's Bearer token. Also: Node returns IPv6
  // hostnames WITH brackets, so a "no dot means local" rule classified every
  // IPv6 literal, public ones included, as private.
  const home = makeTmpHome({ keys: { GRAPHIFY_TOKEN: "sk-secret" } });
  try {
    const bypasses = [
      "http://10.evil.example/mcp",
      "http://127.evil.example/mcp",
      "http://192.168.evil.example/mcp",
      "http://172.16.evil.example/mcp",
      "http://169.254.evil.example/mcp",
      "http://[2001:db8::1]/mcp",
      "http://evil.local.example/mcp",
    ];
    for (const url of bypasses) {
      const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: { GRAPHIFY_URL: url } });
      assert.equal(cfg.ready, false, `${url} must never receive a credential`);
    }
  } finally { home.cleanup(); }
});

test("resolve: rejects a plaintext http endpoint on a public host", () => {
  // QG redo 3: the token comes from keys.json but the URL can come from the
  // environment, so an unvalidated endpoint redirects the credential.
  const home = makeTmpHome({ keys: { GRAPHIFY_TOKEN: "tok" } });
  try {
    const cfg = resolveGraphifyHttpConfig({
      home: home.dir, env: { GRAPHIFY_URL: "http://evil.example.com/mcp" },
    });
    assert.equal(cfg.url, "", "public plaintext host must not resolve");
    assert.equal(cfg.ready, false);
  } finally { home.cleanup(); }
});

test("resolve: accepts https anywhere and http on LAN/loopback", () => {
  const home = makeTmpHome({ keys: { GRAPHIFY_TOKEN: "tok" } });
  try {
    const accepted = [
      "https://graph.example.com/mcp",   // TLS — any host
      "http://localhost:8080/mcp",       // loopback
      "http://127.0.0.1:8080/mcp",       // loopback
      "http://192.168.1.13:8080/mcp",    // private range (the home AI lab)
      "http://10.0.0.5:8080/mcp",        // private range
      "http://nas.local:8080/mcp",       // mDNS
      "http://lab:8080/mcp",             // single-label host (/etc/hosts, DNS search)
    ];
    for (const url of accepted) {
      const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: { GRAPHIFY_URL: url } });
      assert.equal(cfg.url, url, `${url} must resolve`);
    }
    for (const url of ["ftp://host/mcp", "not-a-url", "http://8.8.8.8/mcp"]) {
      const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: { GRAPHIFY_URL: url } });
      assert.equal(cfg.url, "", `${url} must be rejected`);
    }
  } finally { home.cleanup(); }
});

test("resolve: enabled:false forces not-ready even with url + token", () => {
  const home = makeTmpHome({
    config: { knowledge: { graphify: { enabled: false, url: "http://x/mcp" } } },
    keys: { GRAPHIFY_TOKEN: "t" },
  });
  try {
    const cfg = resolveGraphifyHttpConfig({ home: home.dir, env: {} });
    assert.equal(cfg.enabled, false);
    assert.equal(cfg.ready, false);
  } finally { home.cleanup(); }
});


// ─── registerGraphifyHttpMcp ────────────────────────────────────────────


test("register: skips on a non-Claude runtime", () => {
  const r = registerGraphifyHttpMcp({ runtime: "codex", url: "http://x/mcp", token: "t" });
  assert.equal(r.action, "skipped");
  assert.equal(r.reason, "runtime-not-claude-code");
});

test("register: skips when url or token missing", () => {
  const mock = makeMockClaude();
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({ runtime: "claude-code", url: "", token: "t" });
      assert.equal(r.action, "skipped");
      assert.equal(r.reason, "not-configured");
    });
  } finally { mock.cleanup(); }
});

test("register: registers when not yet present", () => {
  const mock = makeMockClaude({ getUrl: "" }); // unregistered
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({ runtime: "claude-code", url: "http://lab:8080/mcp", token: "t" });
      assert.equal(r.action, "registered");
    });
  } finally { mock.cleanup(); }
});

test("register: already-present when same URL registered", () => {
  const mock = makeMockClaude({ getUrl: "http://lab:8080/mcp" });
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({ runtime: "claude-code", url: "http://lab:8080/mcp", token: "t" });
      assert.equal(r.action, "already-present");
    });
  } finally { mock.cleanup(); }
});

test("register: re-registers when the URL changed", () => {
  const mock = makeMockClaude({ getUrl: "http://old:8080/mcp" });
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({ runtime: "claude-code", url: "http://new:9090/mcp", token: "t" });
      assert.equal(r.action, "re-registered");
    });
  } finally { mock.cleanup(); }
});

test("register: captures failure as 'failed' with reason", () => {
  const mock = makeMockClaude({ getUrl: "", addExit: 1, addStderr: "bad url" });
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({ runtime: "claude-code", url: "http://x/mcp", token: "t" });
      assert.equal(r.action, "failed");
      assert.match(r.reason, /bad url/);
    });
  } finally { mock.cleanup(); }
});

test("register: never echoes a Bearer token into the failure reason", () => {
  // QG finding: the captured stderr flows to console.log in index/update.js.
  const secret = "sk-live-supersecret-token-value";
  const mock = makeMockClaude({
    getUrl: "", addExit: 1, addStderr: `refused header Authorization: Bearer ${secret}`,
  });
  try {
    withMockedPath([mock.dir], () => {
      const r = registerGraphifyHttpMcp({
        runtime: "claude-code", url: "http://x/mcp", token: secret,
      });
      assert.equal(r.action, "failed");
      assert.ok(!r.reason.includes(secret), "token must never appear in the reason");
      assert.match(r.reason, /Bearer \*\*\*/);
    });
  } finally { mock.cleanup(); }
});


// ─── configureGraphifyHttp orchestration (headless) ─────────────────────


test("configure: skipped/not-configured in headless run with empty config", async () => {
  const mock = makeMockClaude();
  const home = makeTmpHome();
  try {
    const r = await withMockedPath([mock.dir], () =>
      configureGraphifyHttp({ runtime: "claude-code", home: home.dir }));
    assert.equal(r.action, "skipped");
    assert.equal(r.reason, "not-configured");
  } finally { mock.cleanup(); home.cleanup(); }
});

test("configure: registers when saved config is ready", async () => {
  const mock = makeMockClaude({ getUrl: "" });
  const home = makeTmpHome({
    config: { knowledge: { graphify: { enabled: true, url: "http://lab:8080/mcp" } } },
    keys: { GRAPHIFY_TOKEN: "tok" },
  });
  try {
    const r = await withMockedPath([mock.dir], () =>
      configureGraphifyHttp({ runtime: "claude-code", home: home.dir }));
    assert.equal(r.action, "registered");
  } finally { mock.cleanup(); home.cleanup(); }
});

test("configure: skipped when disabled", async () => {
  const mock = makeMockClaude();
  const home = makeTmpHome({
    config: { knowledge: { graphify: { enabled: false } } },
  });
  try {
    const r = await withMockedPath([mock.dir], () =>
      configureGraphifyHttp({ runtime: "claude-code", home: home.dir }));
    assert.equal(r.action, "skipped");
    assert.equal(r.reason, "disabled");
  } finally { mock.cleanup(); home.cleanup(); }
});
