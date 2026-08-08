// PR-B5 (N3): the agent-provision PreToolUse(Task) gate finally reaches
// settings.json through the adapter — the executed path — instead of
// living only in config/settings-template.json, which npx arkaos
// install never applies (only the legacy install.sh merges the
// template).
//
// Functional coverage: configureHooks registers the Task-matcher entry
// (POSIX, script present), stays idempotent, degrades to no entry when
// the script is missing, and preserves foreign settings keys. Wiring
// coverage: install AND update copy the script, so the conditional
// registration has something to point at on real machines.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync,
} from "node:fs";
import { tmpdir, platform } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const adapter = (
  await import(pathToFileURL(join(ROOT, "installer", "adapters", "claude-code.js")))
).default;

const IS_WINDOWS = platform() === "win32";

function makeInstallDir(withProvisionScript) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-provision-"));
  const hooksDir = join(dir, "install", "config", "hooks");
  mkdirSync(hooksDir, { recursive: true });
  // The universal hooks the adapter always registers need no source
  // files — hookEntry() builds paths without checking existence. Only
  // the agent-provision entry is conditional on the script.
  if (withProvisionScript) {
    writeFileSync(join(hooksDir, "agent-provision.sh"), "#!/usr/bin/env bash\n");
  }
  return {
    installDir: join(dir, "install"),
    settingsFile: join(dir, "settings.json"),
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function provisionEntries(settingsFile) {
  const settings = JSON.parse(readFileSync(settingsFile, "utf-8"));
  return (settings.hooks.PreToolUse || []).filter((e) => e.matcher === "Task");
}

test("configureHooks registers the Task-matcher provisioning gate (POSIX)", { skip: IS_WINDOWS }, () => {
  const { installDir, settingsFile, cleanup } = makeInstallDir(true);
  try {
    adapter.configureHooks({ settingsFile }, installDir);
    const entries = provisionEntries(settingsFile);
    assert.equal(entries.length, 1, "exactly one Task-matcher entry");
    const hook = entries[0].hooks[0];
    assert.ok(
      hook.command.endsWith("agent-provision.sh"),
      "the entry must point at the provisioning script"
    );
    assert.equal(hook.timeout, 10, "template parity: 10s timeout");
    assert.equal(hook.type, "command");
  } finally {
    cleanup();
  }
});

test("configureHooks is idempotent — a re-run never duplicates the gate", { skip: IS_WINDOWS }, () => {
  const { installDir, settingsFile, cleanup } = makeInstallDir(true);
  try {
    adapter.configureHooks({ settingsFile }, installDir);
    adapter.configureHooks({ settingsFile }, installDir);
    assert.equal(provisionEntries(settingsFile).length, 1);
  } finally {
    cleanup();
  }
});

test("a missing script registers no entry — never a dead command", { skip: IS_WINDOWS }, () => {
  const { installDir, settingsFile, cleanup } = makeInstallDir(false);
  try {
    adapter.configureHooks({ settingsFile }, installDir);
    assert.equal(provisionEntries(settingsFile).length, 0);
  } finally {
    cleanup();
  }
});

test("registering the gate preserves foreign settings keys", { skip: IS_WINDOWS }, () => {
  const { installDir, settingsFile, cleanup } = makeInstallDir(true);
  try {
    writeFileSync(
      settingsFile,
      JSON.stringify({ theme: "dark", hooks: { MyCustomEvent: [{ hooks: [] }] } })
    );
    adapter.configureHooks({ settingsFile }, installDir);
    const settings = JSON.parse(readFileSync(settingsFile, "utf-8"));
    assert.equal(settings.theme, "dark", "unknown top-level keys survive");
    assert.ok(settings.hooks.MyCustomEvent, "foreign hook events survive");
    assert.equal(provisionEntries(settingsFile).length, 1);
  } finally {
    cleanup();
  }
});

test("install and update both copy agent-provision.sh (wiring)", () => {
  // Source-level pin, same style as hook-consistency.test.js: the
  // conditional registration above is dead weight unless BOTH deploy
  // paths put the script into ~/.arkaos/config/hooks/.
  const indexSrc = readFileSync(join(ROOT, "installer", "index.js"), "utf-8");
  const updateSrc = readFileSync(join(ROOT, "installer", "update.js"), "utf-8");
  const adapterSrc = readFileSync(
    join(ROOT, "installer", "adapters", "claude-code.js"), "utf-8"
  );
  assert.ok(
    indexSrc.includes('"agent-provision.sh"'),
    "installer/index.js must copy the gate script"
  );
  assert.ok(
    updateSrc.includes('"agent-provision.sh"'),
    "installer/update.js must copy the gate script"
  );
  assert.ok(
    adapterSrc.includes('matcher: "Task"'),
    "the adapter must scope the gate to the Task tool"
  );
  assert.ok(
    existsSync(join(ROOT, "config", "hooks", "agent-provision.sh")),
    "the source script must exist in config/hooks/"
  );
});
