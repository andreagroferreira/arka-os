// F2-7c — persisted skills-deploy mode (deprecation window, user-data
// v2.19 pattern). HOME is sandboxed per test via env override... which
// node:os homedir() ignores, so the module reads the REAL home — these
// tests therefore exercise resolveSkillsMode's pure decision ladder
// through its inputs and restore any file they write.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync, rmSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

import {
  deprecationNotice, readSkillsMode, resolveSkillsMode, writeSkillsMode,
} from "../../installer/skills-mode.js";

const MODE_FILE = join(homedir(), ".arkaos", "skills-mode.json");

function withModeFile(body, fn) {
  const existed = existsSync(MODE_FILE);
  const original = existed ? readFileSync(MODE_FILE, "utf-8") : null;
  try {
    if (body === null) {
      rmSync(MODE_FILE, { force: true });
    } else {
      mkdirSync(join(homedir(), ".arkaos"), { recursive: true });
      writeFileSync(MODE_FILE, body);
    }
    return fn();
  } finally {
    if (existed) {
      writeFileSync(MODE_FILE, original);
    } else {
      rmSync(MODE_FILE, { force: true });
    }
  }
}

test("explicit --skills flag wins and persists", () => {
  withModeFile(null, () => {
    const result = resolveSkillsMode({ flag: "full", fresh: true });
    assert.deepEqual(result, { mode: "full", deprecated: false });
    assert.equal(readSkillsMode(), "full");
  });
});

test("persisted mode is preserved on update (no flag)", () => {
  withModeFile('{"mode":"curated"}\n', () => {
    const result = resolveSkillsMode({ flag: "", fresh: false });
    assert.deepEqual(result, { mode: "curated", deprecated: false });
  });
});

test("fresh install without a mode file defaults to curated and persists", () => {
  withModeFile(null, () => {
    const result = resolveSkillsMode({ flag: "", fresh: true });
    assert.deepEqual(result, { mode: "curated", deprecated: false });
    assert.equal(readSkillsMode(), "curated");
  });
});

test("legacy update (no mode file) stays FULL and flags the deprecation", () => {
  withModeFile(null, () => {
    const result = resolveSkillsMode({ flag: "", fresh: false });
    assert.deepEqual(result, { mode: "full", deprecated: true },
      "an update must never silently shrink an installed surface");
    assert.equal(readSkillsMode(), null,
      "legacy full is NOT persisted — the operator decides");
  });
});

test("corrupt or invalid mode file is ignored, not fatal", () => {
  withModeFile("{broken", () => {
    assert.equal(readSkillsMode(), null);
  });
  withModeFile('{"mode":"yolo"}', () => {
    assert.equal(readSkillsMode(), null);
    assert.equal(writeSkillsMode("yolo"), false);
  });
});

test("deprecation notice names both the switch and the opt-out", () => {
  const notice = deprecationNotice();
  assert.match(notice, /--skills curated/);
  assert.match(notice, /--skills full/);
  assert.match(notice, /arkaos-<dept>@arkaos/);
});
