// Tests for installer/output-style.js (Interaction Reform PR1).
//
// Contract: installOutputStyles copies config/output-styles/*.md into
// ~/.claude/output-styles/ unconditionally (idempotent overwrite — the
// repo is the source of truth for the FILE). seedOutputStyleDefault
// writes `outputStyle: "ArkaOS"` into ~/.claude/settings.json ONLY when
// the key is absent — any explicit operator choice (including
// "default") is preserved.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  chmodSync, mkdtempSync, mkdirSync, writeFileSync, readFileSync,
  existsSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { installOutputStyles, seedOutputStyleDefault } =
  await import(join(ROOT, "installer", "output-style.js"));

const SOURCE_DIR = join(ROOT, "config", "output-styles");

function makeTmpHome() {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-style-test-"));
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function writeSettings(home, payload) {
  const path = join(home, ".claude", "settings.json");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(payload, null, 2));
  return path;
}

test("installOutputStyles copies the tracked style into HOME", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = installOutputStyles({ sourceDir: SOURCE_DIR, home: dir });
    assert.equal(result.skipped, null);
    assert.ok(result.copied >= 1);
    const dest = join(dir, ".claude", "output-styles", "arkaos.md");
    assert.ok(existsSync(dest));
    assert.match(readFileSync(dest, "utf-8"), /name: ArkaOS/);
  } finally {
    cleanup();
  }
});

test("installOutputStyles is idempotent and refreshes stale copies", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const dest = join(dir, ".claude", "output-styles", "arkaos.md");
    mkdirSync(dirname(dest), { recursive: true });
    writeFileSync(dest, "stale content");
    installOutputStyles({ sourceDir: SOURCE_DIR, home: dir });
    assert.match(readFileSync(dest, "utf-8"), /name: ArkaOS/);
  } finally {
    cleanup();
  }
});

test("installOutputStyles skips gracefully when source is missing", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = installOutputStyles({
      sourceDir: join(dir, "does-not-exist"),
      home: dir,
    });
    assert.equal(result.skipped, "source-not-found");
  } finally {
    cleanup();
  }
});

test("seed sets outputStyle when key is absent", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const path = writeSettings(dir, { statusLine: { type: "command" } });
    const result = seedOutputStyleDefault({ home: dir });
    assert.equal(result.action, "created");
    const settings = JSON.parse(readFileSync(path, "utf-8"));
    assert.equal(settings.outputStyle, "ArkaOS");
    assert.deepEqual(settings.statusLine, { type: "command" });
  } finally {
    cleanup();
  }
});

test("seed preserves explicit operator choice, including 'default'", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    for (const chosen of ["default", "MyStyle"]) {
      const path = writeSettings(dir, { outputStyle: chosen });
      const result = seedOutputStyleDefault({ home: dir });
      assert.equal(result.action, "noop");
      assert.equal(result.value, chosen);
      assert.equal(
        JSON.parse(readFileSync(path, "utf-8")).outputStyle,
        chosen,
      );
    }
  } finally {
    cleanup();
  }
});

test("seed skips when settings.json is absent or unparseable", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    assert.equal(
      seedOutputStyleDefault({ home: dir }).skipped,
      "claude-settings-not-found",
    );
    const path = writeSettings(dir, {});
    writeFileSync(path, "{not json");
    assert.equal(
      seedOutputStyleDefault({ home: dir }).skipped,
      "settings-not-parseable",
    );
  } finally {
    cleanup();
  }
});

test("seed returns write-failed instead of throwing on read-only HOME", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const path = writeSettings(dir, {});
    // Make the directory read-only so the .tmp write fails (QG M1).
    const claudeDir = dirname(path);
    chmodSync(claudeDir, 0o555);
    try {
      const result = seedOutputStyleDefault({ home: dir });
      assert.equal(result.skipped, "write-failed");
    } finally {
      chmodSync(claudeDir, 0o755);
    }
  } finally {
    cleanup();
  }
});

test("seed is a no-op for non-claude-code runtimes", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    writeSettings(dir, {});
    const result = seedOutputStyleDefault({ runtime: "codex", home: dir });
    assert.equal(result.skipped, "runtime-not-claude-code");
  } finally {
    cleanup();
  }
});
