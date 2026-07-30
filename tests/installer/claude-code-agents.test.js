// Tests for deployProjectAgents (PR-4 evidence Quality Gate).
//
// The claude-code adapter deploys the packaged Quality Gate / squad-lead
// subagent definitions (config/claude-agents/*.md — .claude/ is gitignored
// in the ArkaOS repo) into a project's .claude/agents/ directory during
// `npx arkaos init`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync,
  readdirSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { deployProjectAgents, LEGACY_PERSONAS } = await import(
  join(ROOT, "installer", "adapters", "claude-code.js")
);

// Spot-check list — full-catalog count is asserted dynamically below.
const EXPECTED_AGENTS = [
  "marta-cqo.md",
  "eduardo-copy.md",
  "francisca-tech.md",
  "paulo-tech-lead.md",
  // PR-4 prompt-surface (2026-07-08): behavioral-compiler pilot output —
  // generated from departments/dev/agents/*.yaml, single source there.
  "architect.md",
  "backend-dev.md",
  "dba.md",
  "devops-eng.md",
  "frontend-dev.md",
  "qa-eng.md",
  "research-assistant.md",
  "security-eng.md",
  // Full-catalog rollout (2026-07-09): every department compiles; stem
  // collisions are department-prefixed; sub-squad nesting is included.
  "cfo.md",
  "cto.md",
  "ecom-cro-specialist.md",
  "landing-cro-specialist.md",
  "laravel-eng.md",
];

const PACKAGED_AGENT_COUNT = readdirSync(join(ROOT, "config", "claude-agents"))
  .filter((f) => f.endsWith(".md")).length;

function makeTmpDir(prefix) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

test("repo ships the QG/lead + compiled full-catalog agent definitions", () => {
  // 82 agent YAMLs → 78 compiled + 4 hand-written.
  assert.ok(
    PACKAGED_AGENT_COUNT >= 80,
    `expected the full compiled catalog, found ${PACKAGED_AGENT_COUNT}`,
  );
  for (const file of EXPECTED_AGENTS) {
    const path = join(ROOT, "config", "claude-agents", file);
    assert.ok(existsSync(path), `${file} must exist in config/claude-agents/`);
    const text = readFileSync(path, "utf-8");
    assert.match(text, /^---\n/, `${file} must start with YAML frontmatter`);
    assert.match(text, /\nmodel: (opus|sonnet|haiku)\n/, `${file} needs a model`);
  }
});

test("deploys packaged agent definitions into the project", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-test-");
  try {
    const count = deployProjectAgents(dir, ROOT);
    assert.equal(count, PACKAGED_AGENT_COUNT);
    for (const file of EXPECTED_AGENTS) {
      assert.ok(
        existsSync(join(dir, ".claude", "agents", file)),
        `${file} should be deployed`,
      );
    }
  } finally {
    cleanup();
  }
});

test("missing source directory is a silent no-op", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-nosrc-");
  const { dir: emptyRoot, cleanup: cleanupRoot } = makeTmpDir("arkaos-empty-root-");
  try {
    const count = deployProjectAgents(dir, emptyRoot);
    assert.equal(count, 0);
    assert.ok(!existsSync(join(dir, ".claude", "agents")));
  } finally {
    cleanup();
    cleanupRoot();
  }
});

test("does not delete user-authored agent files", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-merge-");
  try {
    const userAgent = join(dir, ".claude", "agents", "my-custom-agent.md");
    mkdirSync(dirname(userAgent), { recursive: true });
    writeFileSync(userAgent, "---\nname: my-custom-agent\n---\n");

    deployProjectAgents(dir, ROOT);
    assert.ok(existsSync(userAgent), "user agent must be preserved");
    assert.ok(existsSync(join(dir, ".claude", "agents", "marta-cqo.md")));
  } finally {
    cleanup();
  }
});

test("re-deploy overwrites ArkaOS-owned definitions by name", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-redeploy-");
  try {
    deployProjectAgents(dir, ROOT);
    const target = join(dir, ".claude", "agents", "marta-cqo.md");
    writeFileSync(target, "stale local edit\n");

    deployProjectAgents(dir, ROOT);
    const text = readFileSync(target, "utf-8");
    assert.match(text, /name: marta-cqo/, "redeploy restores packaged content");
  } finally {
    cleanup();
  }
});

// ─── PR-B5 (N5): v1 persona retirement ──────────────────────────────────
//
// Verified live on 2026-07-30: a real project carried cqo.md,
// copy-director.md and tech-ux-director.md (v1, no QGVerdict contract)
// and NONE of the actual reviewers — every Quality Gate there dispatched
// a contract-less persona. Deploy now retires the known v1 names into
// .arkaos-legacy/ before copying the current catalog.

test("retires v1 personas into .arkaos-legacy/ and deploys reviewers", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-retire-");
  try {
    const agentsDir = join(dir, ".claude", "agents");
    mkdirSync(agentsDir, { recursive: true });
    writeFileSync(join(agentsDir, "cqo.md"), "v1 persona body\n");
    writeFileSync(join(agentsDir, "architect.md"), "stale but live name\n");

    deployProjectAgents(dir, ROOT);

    assert.ok(
      !existsSync(join(agentsDir, "cqo.md")),
      "a v1 persona must leave the dispatch path"
    );
    assert.equal(
      readFileSync(join(agentsDir, ".arkaos-legacy", "cqo.md"), "utf-8"),
      "v1 persona body\n",
      "retired verbatim — renamed, never deleted"
    );
    assert.match(
      readFileSync(join(agentsDir, "architect.md"), "utf-8"),
      /name: architect/,
      "a name still shipped by ArkaOS is overwritten by source, not retired"
    );
    assert.ok(!existsSync(join(agentsDir, ".arkaos-legacy", "architect.md")));
    assert.ok(existsSync(join(agentsDir, "francisca-tech.md")));
  } finally {
    cleanup();
  }
});

test("retire collision appends a numeric suffix, never overwrites", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-retire-collide-");
  try {
    const agentsDir = join(dir, ".claude", "agents");
    const legacyDir = join(agentsDir, ".arkaos-legacy");
    mkdirSync(legacyDir, { recursive: true });
    writeFileSync(join(legacyDir, "cqo.md"), "first retirement\n");
    writeFileSync(join(agentsDir, "cqo.md"), "second retirement\n");

    deployProjectAgents(dir, ROOT);

    assert.equal(
      readFileSync(join(legacyDir, "cqo.md"), "utf-8"),
      "first retirement\n",
      "an earlier retirement is never overwritten"
    );
    assert.equal(
      readFileSync(join(legacyDir, "cqo-1.md"), "utf-8"),
      "second retirement\n",
      "the collision lands under a numeric suffix"
    );
  } finally {
    cleanup();
  }
});

test("user files outside the legacy list are never retired", () => {
  const { dir, cleanup } = makeTmpDir("arkaos-agents-retire-user-");
  try {
    const agentsDir = join(dir, ".claude", "agents");
    mkdirSync(agentsDir, { recursive: true });
    writeFileSync(join(agentsDir, "my-custom-agent.md"), "mine\n");

    deployProjectAgents(dir, ROOT);

    assert.equal(
      readFileSync(join(agentsDir, "my-custom-agent.md"), "utf-8"),
      "mine\n",
      "a user agent stays exactly where it was"
    );
    assert.ok(!existsSync(join(agentsDir, ".arkaos-legacy", "my-custom-agent.md")));
  } finally {
    cleanup();
  }
});

test("LEGACY_PERSONAS never intersects the shipped source set", () => {
  // The double guard in code (named AND absent from source) is backed
  // structurally here: a v1 name returning to config/claude-agents/
  // must be removed from the retirement list first.
  const shipped = readdirSync(join(ROOT, "config", "claude-agents"))
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.slice(0, -3));
  const overlap = shipped.filter((name) => LEGACY_PERSONAS.has(name));
  assert.deepEqual(
    overlap,
    [],
    "a shipped agent name may never sit on the retirement list"
  );
});
