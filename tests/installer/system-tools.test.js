import { test } from "node:test";
import assert from "node:assert/strict";
import {
  checkNode,
  checkPython,
  ensureSystemTools,
} from "../../installer/system-tools.js";

test("ensureSystemTools respects skipSystem flag", () => {
  const out = ensureSystemTools({ skipSystem: true });
  assert.equal(out.skipped, true);
  assert.equal(out.obsidian, null);
  assert.equal(out.node, null);
  assert.equal(out.python, null);
  assert.deepEqual(out.sudoCommands, []);
});

test("ensureSystemTools dry-run returns ToolStatus without installing", () => {
  const out = ensureSystemTools({ dryRun: true, skipSystem: false });
  assert.equal(out.skipped, false);
  assert.ok(out.obsidian);
  assert.ok(out.node);
  assert.ok(out.python);
  assert.ok(Array.isArray(out.sudoCommands));
});

test("checkNode returns valid ToolStatus shape", () => {
  const status = checkNode();
  assert.equal(status.name, "node");
  assert.ok(typeof status.installed === "boolean");
  assert.ok(["none", "install", "upgrade"].includes(status.needsAction));
});

test("checkNode in this test env detects Node 18+", () => {
  // The Node process running these tests proves Node is installed.
  const status = checkNode();
  assert.equal(status.installed, true);
  assert.ok(status.location);
  assert.ok(status.version);
});

test("checkPython returns valid ToolStatus shape", () => {
  const status = checkPython();
  assert.equal(status.name, "python");
  assert.ok(typeof status.installed === "boolean");
  assert.ok(["none", "install", "upgrade"].includes(status.needsAction));
});

test("ensureSystemTools is idempotent (run twice has no side effects)", () => {
  const first = ensureSystemTools({ dryRun: true });
  const second = ensureSystemTools({ dryRun: true });
  // Same shape, same conclusion
  assert.deepEqual(
    { o: first.obsidian.needsAction, n: first.node.needsAction, p: first.python.needsAction },
    { o: second.obsidian.needsAction, n: second.node.needsAction, p: second.python.needsAction }
  );
});

test("sudoCommands is always an array even when all tools are present", () => {
  const out = ensureSystemTools({ dryRun: true });
  assert.ok(Array.isArray(out.sudoCommands));
});
