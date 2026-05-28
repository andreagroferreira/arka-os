import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");

/**
 * Extract the hookNames array literal from a JS source file.
 * Looks for `const hookNames = [ ... ];` and returns the list of
 * quoted string values inside it.
 */
function extractHookNames(filePath) {
  const src = readFileSync(filePath, "utf-8");
  // Match the first `const hookNames = [ ... ];` block (non-greedy, single-line
  // entries separated by commas and optional whitespace/newlines).
  const match = src.match(/const hookNames\s*=\s*\[([\s\S]*?)\];/);
  if (!match) throw new Error(`hookNames array not found in ${filePath}`);
  // Pull out every double-quoted string value from inside the brackets.
  return [...match[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

const REQUIRED_HOOKS = ["pre-tool-use", "stop"];

test("installer hookNames arrays stay in lockstep", () => {
  const updateHooks = extractHookNames(join(ROOT, "installer", "update.js"));
  const indexHooks = extractHookNames(join(ROOT, "installer", "index.js"));

  // Set equality: every entry in index.js must appear in update.js and vice-versa.
  const updateSet = new Set(updateHooks);
  const indexSet = new Set(indexHooks);

  for (const name of indexSet) {
    assert.ok(
      updateSet.has(name),
      `update.js hookNames is missing "${name}" which exists in index.js`,
    );
  }

  for (const name of updateSet) {
    assert.ok(
      indexSet.has(name),
      `index.js hookNames is missing "${name}" which exists in update.js`,
    );
  }

  assert.equal(
    updateHooks.length,
    indexHooks.length,
    `hookNames length mismatch: update.js=${updateHooks.length} index.js=${indexHooks.length}`,
  );
});

test("both hookNames arrays explicitly contain pre-tool-use and stop", () => {
  const updateHooks = new Set(
    extractHookNames(join(ROOT, "installer", "update.js")),
  );
  const indexHooks = new Set(
    extractHookNames(join(ROOT, "installer", "index.js")),
  );

  for (const hook of REQUIRED_HOOKS) {
    assert.ok(
      updateHooks.has(hook),
      `update.js hookNames is missing required hook "${hook}" — specialist enforcement will be dead on update`,
    );
    assert.ok(
      indexHooks.has(hook),
      `index.js hookNames is missing required hook "${hook}"`,
    );
  }
});
