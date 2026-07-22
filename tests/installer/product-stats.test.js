// Foundation PR-3 QG minor — product counts derived at runtime, never
// hand-typed (docs-as-code rule). The install summary previously said
// "65 agents / 244+ skills" while the shipped artifacts carry 89/331 —
// numbers in output MUST come from the artifacts themselves.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { readProductStats, productStatsLines } from "../../installer/product-stats.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function withFixtureRepo(setup, fn) {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-stats-test-"));
  try {
    setup(dir);
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeMinimalFixture(dir) {
  mkdirSync(join(dir, "knowledge"), { recursive: true });
  writeFileSync(
    join(dir, "knowledge", "agents-registry-v2.json"),
    JSON.stringify({ _meta: {}, agents: [{ id: "a" }, { id: "b" }, { id: "c" }] }),
  );
  writeFileSync(
    join(dir, "knowledge", "skills-manifest.json"),
    JSON.stringify({
      _meta: {},
      structural: { main: "arka", hubs: ["arka-dev"], meta: ["arka-flow", "arka-forge"] },
      skills: { "code-review": {}, "db-design": {} },
    }),
  );
  mkdirSync(join(dir, "departments", "dev"), { recursive: true });
  mkdirSync(join(dir, "departments", "marketing"), { recursive: true });
  // A stray file must not count as a department.
  writeFileSync(join(dir, "departments", "README.md"), "not a department");
}

test("readProductStats derives all three counts from a fixture repo", () => {
  withFixtureRepo(writeMinimalFixture, (dir) => {
    const stats = readProductStats(dir);
    assert.equal(stats.agents, 3);
    assert.equal(stats.departments, 2, "files in departments/ must not count");
    // skills map (2) + structural: main (1) + hubs (1) + meta (2) = 6
    assert.equal(stats.skills, 6);
  });
});

test("skills manifest without structural counts only the skills map", () => {
  withFixtureRepo(
    (dir) => {
      writeMinimalFixture(dir);
      writeFileSync(
        join(dir, "knowledge", "skills-manifest.json"),
        JSON.stringify({ skills: { a: {}, b: {}, c: {} } }),
      );
    },
    (dir) => {
      assert.equal(readProductStats(dir).skills, 3);
    },
  );
});

test("missing sources yield null per field, never a throw", () => {
  withFixtureRepo(() => {}, (dir) => {
    const stats = readProductStats(dir);
    assert.deepEqual(stats, { agents: null, departments: null, skills: null });
  });
});

test("a corrupt source nulls only its own field", () => {
  withFixtureRepo(
    (dir) => {
      writeMinimalFixture(dir);
      writeFileSync(join(dir, "knowledge", "agents-registry-v2.json"), "{broken");
    },
    (dir) => {
      const stats = readProductStats(dir);
      assert.equal(stats.agents, null);
      assert.equal(stats.departments, 2);
      assert.equal(stats.skills, 6);
    },
  );
});

test("malformed shapes (agents not an array, skills an array) yield null", () => {
  withFixtureRepo(
    (dir) => {
      writeMinimalFixture(dir);
      writeFileSync(
        join(dir, "knowledge", "agents-registry-v2.json"),
        JSON.stringify({ agents: { a: 1 } }),
      );
      writeFileSync(
        join(dir, "knowledge", "skills-manifest.json"),
        JSON.stringify({ skills: ["a", "b"] }),
      );
    },
    (dir) => {
      const stats = readProductStats(dir);
      assert.equal(stats.agents, null);
      assert.equal(stats.skills, null);
    },
  );
});

// ── Integration: the REAL repo is the fixture ─────────────────────────────
// The expected values are read from the shipped artifacts inside the
// test itself — never hardcoded — so this locks the function against
// format drift in the real files.

test("readProductStats matches the real repo artifacts (no hand-typed numbers)", () => {
  const stats = readProductStats(ROOT);

  const registry = JSON.parse(
    readFileSync(join(ROOT, "knowledge", "agents-registry-v2.json"), "utf-8"),
  );
  assert.equal(stats.agents, registry.agents.length);
  assert.ok(stats.agents > 0, "real repo must report a positive agent count");

  const deptDirs = readdirSync(join(ROOT, "departments"), { withFileTypes: true })
    .filter((e) => e.isDirectory()).length;
  assert.equal(stats.departments, deptDirs);
  assert.ok(stats.departments > 0);

  const manifest = JSON.parse(
    readFileSync(join(ROOT, "knowledge", "skills-manifest.json"), "utf-8"),
  );
  const expectedSkills =
    Object.keys(manifest.skills).length +
    (manifest.structural?.main ? 1 : 0) +
    (manifest.structural?.hubs?.length || 0) +
    (manifest.structural?.meta?.length || 0);
  assert.equal(stats.skills, expectedSkills);
  assert.ok(stats.skills > 0);
});

// ── productStatsLines — null fields omitted, never invented ───────────────

test("productStatsLines renders both lines when all fields present", () => {
  // Arbitrary formatter inputs — real counts are covered by the
  // integration test above, never hand-typed here.
  const lines = productStatsLines({ agents: 7, departments: 4, skills: 12 });
  assert.deepEqual(lines, [
    "Agents:      7 across 4 departments",
    "Skills:      12 backed by enterprise frameworks",
  ]);
});

test("productStatsLines omits null fields instead of inventing numbers", () => {
  assert.deepEqual(productStatsLines({ agents: null, departments: null, skills: null }), []);
  assert.deepEqual(productStatsLines({ agents: 7, departments: null, skills: null }), [
    "Agents:      7",
  ]);
  assert.deepEqual(productStatsLines({ agents: null, departments: 17, skills: 5 }), [
    "Skills:      5 backed by enterprise frameworks",
  ]);
});
