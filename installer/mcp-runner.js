import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { spawnSync } from "node:child_process";

import { getArkaosPython, getRepoRoot } from "./python-resolver.js";

// F2-7a — `npx arkaos mcp start`: run the arka-tools MCP server (stdio)
// outside Claude Code (other runtimes, debugging, CI smoke tests).
//
// Resolution order mirrors production first: mcps/registry.json runs the
// server via `uv --directory <toolsDir> run server.py`, so when uv is on
// PATH we replicate that exact invocation. Fallback is the ArkaOS venv
// python — but NO installer pip path installs `mcp[cli]` (the pyproject
// [mcp] extra exists for tests only), so the fallback preflights
// `import mcp` and fails HONESTLY with both remediations instead of a
// stack trace at first tool call.

export function toolsDir(home = homedir()) {
  return join(home, ".claude", "skills", "arka", "mcp-tools");
}

function uvAvailable(spawn = spawnSync) {
  const probe = spawn("uv", ["--version"], { stdio: "ignore", timeout: 5000 });
  return !probe.error && probe.status === 0;
}

function venvHasMcp(py, spawn = spawnSync) {
  const probe = spawn(py, ["-c", "import mcp"], {
    stdio: "ignore",
    timeout: 15000,
  });
  return !probe.error && probe.status === 0;
}

/**
 * Resolve how to launch the arka-tools server.
 * Returns {cmd, args, kind: "uv"|"venv"} or {error: string}.
 * Injectable deps keep this unit-testable without real binaries.
 */
export function resolveRunner({
  home = homedir(),
  spawn = spawnSync,
  pythonResolver = getArkaosPython,
} = {}) {
  const dir = toolsDir(home);
  if (!existsSync(join(dir, "server.py"))) {
    return {
      error:
        "arka-tools is not deployed (missing " + join(dir, "server.py") +
        ").\nRun: npx arkaos install",
    };
  }
  if (uvAvailable(spawn)) {
    // Exact replica of the mcps/registry.json invocation Claude Code uses.
    return { kind: "uv", cmd: "uv", args: ["--directory", dir, "run", "server.py"] };
  }
  const py = pythonResolver();
  if (!py) {
    return { error: "No Python found. Run: npx arkaos install" };
  }
  if (!venvHasMcp(py, spawn)) {
    return {
      error:
        "arka-tools needs the MCP SDK and neither runner is ready. Fix one of:\n" +
        "  1. Install uv (recommended): https://docs.astral.sh/uv\n" +
        "  2. ~/.arkaos/venv/bin/pip install 'mcp[cli]>=1.2.0'",
    };
  }
  return { kind: "venv", cmd: py, args: [join(dir, "server.py")] };
}

/**
 * Start the server in the foreground (stdio transport — the MCP client
 * owns the lifecycle; there is no daemon to manage). Returns the exit
 * code to propagate.
 */
export function startServer({
  write = false,
  home = homedir(),
  spawn = spawnSync,
  pythonResolver = getArkaosPython,
  repoRootResolver = getRepoRoot,
  log = console.error,
} = {}) {
  const runner = resolveRunner({ home, spawn, pythonResolver });
  if (runner.error) {
    log(runner.error);
    return 1;
  }
  const env = { ...process.env };
  // repoRootResolver walks .repo-path/install-manifest — NEVER anchor on
  // the npx cache dir, which `npm cache clean` purges at any time.
  // Injectable so tests assert the positive ARKA_OS path (QG 7a M1).
  const repoRoot = repoRootResolver();
  if (repoRoot) env.ARKA_OS = repoRoot;
  if (write) {
    env.ARKA_TOOLS_WRITE = "1"; // server.py requires the exact value "1"
  }
  log(`arka-tools MCP server starting (${runner.kind}, stdio)` +
    (write ? " — WRITES ENABLED (ARKA_TOOLS_WRITE=1)" : " — read-only"));
  const result = spawn(runner.cmd, runner.args, { stdio: "inherit", env });
  if (result.error) {
    log(`Failed to start: ${result.error.message}`);
    return 1;
  }
  return result.status ?? 0;
}
