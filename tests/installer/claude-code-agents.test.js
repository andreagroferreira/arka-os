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
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { deployProjectAgents } = await import(
  join(ROOT, "installer", "adapters", "claude-code.js")
);

const EXPECTED_AGENTS = [
  "marta-cqo.md",
  "eduardo-copy.md",
  "francisca-tech.md",
  "paulo-tech-lead.md",
];

function makeTmpDir(prefix) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  return { dir, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

test("repo ships the four QG/lead agent definitions", () => {
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
    assert.equal(count, EXPECTED_AGENTS.length);
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
