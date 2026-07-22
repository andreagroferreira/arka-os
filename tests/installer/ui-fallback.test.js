// Foundation PR-3 — the UI facade's graceful-fallback contract.
//
// Rule (.claude/rules/node-installer.md): graceful fallbacks when
// optional dependencies are unavailable. installer/ui.js must NEVER
// throw when @clack/prompts is missing, and its plain mode must print
// the historical installer strings byte-for-byte so headless logs and
// the auto-update daemon output stay stable.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const UI_SRC = join(ROOT, "installer", "ui.js");

const PROBE = [
  `const ui = await getUi();`,
  `ui.step(1, 3, "msg");`,
  `ui.ok("done");`,
  `ui.warn("careful");`,
  `console.log("FANCY:" + ui.isFancy());`,
].join("\n");

function runProbe(uiUrl, extraEnv = {}) {
  const code = `const { getUi } = await import(${JSON.stringify(uiUrl)});\n${PROBE}`;
  return spawnSync(process.execPath, ["--input-type=module", "-e", code], {
    env: { ...process.env, ...extraEnv },
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 15000,
    encoding: "utf-8",
  });
}

function assertPlainOutput(run) {
  assert.equal(run.status, 0, `stderr: ${run.stderr}`);
  const lines = run.stdout.split("\n");
  assert.ok(lines.includes("  [1/3] msg"), `step line missing in: ${run.stdout}`);
  assert.ok(lines.includes("         ✓ done"), `ok line missing in: ${run.stdout}`);
  assert.ok(lines.includes("         ⚠ careful"), `warn line missing in: ${run.stdout}`);
  assert.ok(lines.includes("FANCY:false"), `expected plain mode in: ${run.stdout}`);
}

test("ui.js degrades to plain (never throws) when @clack/prompts cannot resolve", () => {
  // Copy ui.js outside the repo: ESM resolves bare specifiers by walking
  // node_modules up from the IMPORTING file, so from a temp dir the
  // optional deps are genuinely unresolvable — this exercises the real
  // import-failure path, not a simulation.
  const dir = mkdtempSync(join(tmpdir(), "arkaos-ui-test-"));
  try {
    const uiCopy = join(dir, "ui.js");
    copyFileSync(UI_SRC, uiCopy);
    const run = runProbe(pathToFileURL(uiCopy).href);
    assertPlainOutput(run);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("non-TTY stdout forces plain mode even when clack is installed", () => {
  // spawnSync pipes stdout — not a TTY — so isFancy() must be false
  // regardless of whether npm install has provided @clack/prompts.
  const run = runProbe(pathToFileURL(UI_SRC).href);
  assertPlainOutput(run);
});

test("ARKA_UI_PLAIN=1 forces plain mode (user escape hatch)", () => {
  const run = runProbe(pathToFileURL(UI_SRC).href, { ARKA_UI_PLAIN: "1" });
  assertPlainOutput(run);
});

test("CI environments force plain mode", () => {
  const run = runProbe(pathToFileURL(UI_SRC).href, { CI: "true" });
  assertPlainOutput(run);
});
