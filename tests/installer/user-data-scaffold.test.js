// Tests for the ~/.arkaos user-data scaffold (PR28 v2.47.0).
//
// Two responsibilities under test:
//   1. ~/.arkaos/redaction-clients.json — created with empty clients
//      list on fresh installs; preserved if operator already wrote one.
//   2. ~/.arkaos/reorganize-proposals/ — directory created if absent,
//      preserved if present.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync,
  statSync, rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { scaffoldArkaosUserData } = await import(
  join(ROOT, "installer", "user-data-scaffold.js")
);

function makeTmpHome() {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-scaffold-test-"));
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

test("fresh install creates redaction-clients.json with empty list", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = scaffoldArkaosUserData({ home: dir });
    const path = join(dir, ".arkaos", "redaction-clients.json");
    assert.ok(existsSync(path), "redaction-clients.json should be created");
    const cfg = JSON.parse(readFileSync(path, "utf-8"));
    assert.deepEqual(cfg.clients, []);
    assert.match(cfg._doc, /leak scanner/i);
    assert.equal(result.redaction.action, "created");
  } finally {
    cleanup();
  }
});

test("existing redaction-clients.json is preserved", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const path = join(dir, ".arkaos", "redaction-clients.json");
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify({ clients: ["my-client"] }, null, 2));
    const before = readFileSync(path, "utf-8");

    const result = scaffoldArkaosUserData({ home: dir });
    const after = readFileSync(path, "utf-8");
    assert.equal(after, before, "operator-authored config must not be touched");
    assert.equal(result.redaction.action, "preserved");
  } finally {
    cleanup();
  }
});

test("fresh install creates reorganize-proposals directory", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = scaffoldArkaosUserData({ home: dir });
    const path = join(dir, ".arkaos", "reorganize-proposals");
    assert.ok(existsSync(path), "reorganize-proposals dir should be created");
    assert.ok(statSync(path).isDirectory());
    assert.equal(result.proposals.action, "created");
  } finally {
    cleanup();
  }
});

test("existing reorganize-proposals directory is preserved", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const path = join(dir, ".arkaos", "reorganize-proposals");
    mkdirSync(path, { recursive: true });
    writeFileSync(join(path, "2026-05-23.md"), "# old proposal\n");

    const result = scaffoldArkaosUserData({ home: dir });
    assert.ok(
      existsSync(join(path, "2026-05-23.md")),
      "existing proposal file must survive",
    );
    assert.equal(result.proposals.action, "preserved");
  } finally {
    cleanup();
  }
});

test("scaffold is idempotent across repeat runs", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const r1 = scaffoldArkaosUserData({ home: dir });
    assert.equal(r1.redaction.action, "created");
    assert.equal(r1.proposals.action, "created");

    const r2 = scaffoldArkaosUserData({ home: dir });
    assert.equal(r2.redaction.action, "preserved");
    assert.equal(r2.proposals.action, "preserved");

    const r3 = scaffoldArkaosUserData({ home: dir });
    assert.equal(r3.redaction.action, "preserved");
    assert.equal(r3.proposals.action, "preserved");
  } finally {
    cleanup();
  }
});
