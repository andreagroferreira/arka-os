import { test } from "node:test";
import assert from "node:assert/strict";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  bundleDir,
  listBundleFiles,
  readBundleFile,
} from "../../installer/harness-bundle.js";

// The adapters used to write pointers at
// ~/.arkaos/config/<runtime>-instructions.md — a file nothing ever
// created. These tests pin the replacement: bundles resolve inside the
// package, missing bundles return null (callers fall back loudly), and
// every adapter-consumed path actually exists in the committed tree.

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("bundleDir resolves inside the package harness/ tree", () => {
  assert.equal(bundleDir("codex"), join(REPO_ROOT, "harness", "codex"));
});

test("every adapter-consumed bundle file exists and is non-trivial", () => {
  for (const [target, rel] of [
    ["codex", "AGENTS.md"],
    ["gemini", "GEMINI.md"],
  ]) {
    const content = readBundleFile(target, rel);
    assert.ok(content, `${target}/${rel} missing from committed harness/`);
    assert.ok(
      content.length > 1000,
      `${target}/${rel} suspiciously small — generator output truncated?`
    );
    assert.ok(
      content.includes("harness_gen.py"),
      `${target}/${rel} must declare its generator`
    );
  }
});

test("cursor bundle lists the always-on rule plus one rule per stack", () => {
  const files = listBundleFiles("cursor", "rules");
  assert.ok(files.includes("arkaos.mdc"), "missing always-on cursor rule");
  const stacks = files.filter((f) => f.startsWith("arkaos-stack-"));
  assert.ok(stacks.length >= 7, `expected >=7 stack rules, got ${stacks.length}`);
});

test("missing bundles return null / empty list, never throw", () => {
  assert.equal(readBundleFile("no-such-harness", "AGENTS.md"), null);
  assert.deepEqual(listBundleFiles("no-such-harness", "rules"), []);
});
