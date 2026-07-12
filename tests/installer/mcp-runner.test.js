// F2-7a — `npx arkaos mcp start` runner resolution. All binaries are
// injected (spawn/pythonResolver mocks) so the tests pin the decision
// ladder without real uv/python on the box, and a sandboxed HOME pins
// the deploy-dir requirement.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { resolveRunner, startServer, toolsDir } from "../../installer/mcp-runner.js";

function makeHome({ deployed = true } = {}) {
  const home = mkdtempSync(join(tmpdir(), "arka-mcp-home-"));
  if (deployed) {
    const dir = toolsDir(home);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "server.py"), "# stub\n");
  }
  return home;
}

// spawn mock: behaviour keyed by command name.
function spawnMock({ uv = false, mcpImport = false } = {}, calls = []) {
  return (cmd, args, opts) => {
    calls.push({ cmd, args, opts });
    if (cmd === "uv") return uv ? { status: 0 } : { error: new Error("ENOENT"), status: null };
    if (Array.isArray(args) && args[0] === "-c" && args[1] === "import mcp") {
      return mcpImport ? { status: 0 } : { status: 1 };
    }
    return { status: 0 };
  };
}

test("uv present + deployed → exact registry.json invocation", () => {
  const home = makeHome();
  try {
    const runner = resolveRunner({ home, spawn: spawnMock({ uv: true }) });
    assert.equal(runner.kind, "uv");
    assert.equal(runner.cmd, "uv");
    assert.deepEqual(runner.args,
      ["--directory", toolsDir(home), "run", "server.py"]);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("not deployed → honest error naming the install command", () => {
  const home = makeHome({ deployed: false });
  try {
    const runner = resolveRunner({ home, spawn: spawnMock({ uv: true }) });
    assert.match(runner.error, /not deployed/);
    assert.match(runner.error, /npx arkaos install/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("no uv + venv without mcp SDK → error lists BOTH remediations", () => {
  const home = makeHome();
  try {
    const runner = resolveRunner({
      home,
      spawn: spawnMock({ uv: false, mcpImport: false }),
      pythonResolver: () => "/fake/venv/python3",
    });
    assert.ok(runner.error);
    assert.match(runner.error, /docs\.astral\.sh\/uv/);
    assert.match(runner.error, /pip install 'mcp\[cli\]>=1\.2\.0'/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("no uv + venv WITH mcp SDK → venv runner on server.py", () => {
  const home = makeHome();
  try {
    const runner = resolveRunner({
      home,
      spawn: spawnMock({ uv: false, mcpImport: true }),
      pythonResolver: () => "/fake/venv/python3",
    });
    assert.equal(runner.kind, "venv");
    assert.equal(runner.cmd, "/fake/venv/python3");
    assert.deepEqual(runner.args, [join(toolsDir(home), "server.py")]);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("no uv + no python → install remediation, exit 1", () => {
  const home = makeHome();
  try {
    const logs = [];
    const code = startServer({
      home,
      spawn: spawnMock({ uv: false }),
      pythonResolver: () => null,
      log: (m) => logs.push(m),
    });
    assert.equal(code, 1);
    assert.match(logs.join("\n"), /No Python found/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("--write sets ARKA_TOOLS_WRITE to the exact value '1'; default leaves it unset", () => {
  const home = makeHome();
  try {
    for (const write of [true, false]) {
      const calls = [];
      const spawn = (cmd, args, opts) => {
        calls.push({ cmd, args, opts });
        if (cmd === "uv" && args[0] === "--version") return { status: 0 };
        return { status: 0 };
      };
      const code = startServer({ home, spawn, write, log: () => {} });
      assert.equal(code, 0);
      const serverCall = calls.at(-1);
      assert.equal(serverCall.cmd, "uv");
      if (write) {
        assert.equal(serverCall.opts.env.ARKA_TOOLS_WRITE, "1");
      } else {
        assert.equal(serverCall.opts.env.ARKA_TOOLS_WRITE, undefined);
      }
      assert.equal(serverCall.opts.stdio, "inherit");
    }
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("server exit code propagates (deny/crash is the caller's signal)", () => {
  const home = makeHome();
  try {
    const spawn = (cmd, args) => {
      if (cmd === "uv" && args[0] === "--version") return { status: 0 };
      return { status: 3 };
    };
    assert.equal(startServer({ home, spawn, log: () => {} }), 3);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("runner never shells out through bash or hardcoded npx-cache paths", async () => {
  const { readFileSync } = await import("node:fs");
  const src = readFileSync(
    new URL("../../installer/mcp-runner.js", import.meta.url), "utf-8");
  assert.ok(!/["']bash["']/.test(src), "no bash — Windows-safe by construction");
  assert.ok(!/join\(__dirname/.test(src),
    "no __dirname anchoring — npx cache is volatile (getRepoRoot only)");
});

test("ARKA_OS is set from the injected repo-root resolver (QG 7a M1)", () => {
  const home = makeHome();
  try {
    const calls = [];
    const spawn = (cmd, args, opts) => {
      calls.push({ cmd, args, opts });
      return { status: 0 };
    };
    const code = startServer({
      home, spawn, log: () => {},
      repoRootResolver: () => "/fake/repo/root",
    });
    assert.equal(code, 0);
    assert.equal(calls.at(-1).opts.env.ARKA_OS, "/fake/repo/root");
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("spawn error on the server itself fails with exit 1 and a message (QG 7a M1)", () => {
  const home = makeHome();
  try {
    const logs = [];
    const spawn = (cmd, args) => {
      if (cmd === "uv" && args[0] === "--version") return { status: 0 };
      return { error: new Error("EACCES"), status: null };
    };
    const code = startServer({
      home, spawn, log: (m) => logs.push(m),
      repoRootResolver: () => null,
    });
    assert.equal(code, 1);
    assert.match(logs.join("\n"), /Failed to start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
