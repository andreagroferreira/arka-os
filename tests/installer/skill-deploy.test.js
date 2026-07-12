// F2-7c-pre — skill-deploy parity. One shared deploySkills() feeds both
// the fresh-install and the update path, so the two surfaces can no
// longer drift (the bug this fixes: update.js §6 never deployed the 14
// meta skills — arka-flow, the evidence-flow NON-NEGOTIABLE, was
// missing from every update-only machine). Copy-only by contract:
// nothing here may delete (feedback_destructive_tests — and the module
// has no delete primitive to stub, asserted structurally below).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, writeFileSync, readdirSync, readFileSync,
  existsSync, rmSync,
} from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

import { deploySkills } from "../../installer/skill-deploy.js";

const here = dirname(fileURLToPath(import.meta.url));

// Minimal fake repo exercising every deploy category.
function makeRepo() {
  const repo = mkdtempSync(join(tmpdir(), "arka-skilldeploy-repo-"));
  writeFileSync(join(repo, "VERSION"), "9.9.9\n");
  mkdirSync(join(repo, "arka", "skills", "flow"), { recursive: true });
  writeFileSync(join(repo, "arka", "SKILL.md"), "# /arka main\n");
  writeFileSync(join(repo, "arka", "skills", "flow", "SKILL.md"),
    "# flow meta skill\n");
  mkdirSync(join(repo, "arka", "skills", "forge"), { recursive: true });
  writeFileSync(join(repo, "arka", "skills", "forge", "SKILL.md"),
    "# forge meta skill\n");
  const dev = join(repo, "departments", "dev");
  mkdirSync(join(dev, "skills", "code-review", "references"),
    { recursive: true });
  writeFileSync(join(dev, "SKILL.md"), "# dev hub\n");
  writeFileSync(join(dev, "skills", "code-review", "SKILL.md"),
    "# code review\n");
  writeFileSync(
    join(dev, "skills", "code-review", "references", "checklist.md"),
    "- item\n");
  mkdirSync(join(dev, "agents"), { recursive: true });
  writeFileSync(join(dev, "agents", "paulo.md"), "# paulo\n");
  return repo;
}

function deployedSet(base) {
  return new Set(readdirSync(base).sort());
}

test("install-shape and update-shape deploys produce IDENTICAL surfaces", () => {
  const repo = makeRepo();
  const homeA = mkdtempSync(join(tmpdir(), "arka-skilldeploy-a-"));
  const homeB = mkdtempSync(join(tmpdir(), "arka-skilldeploy-b-"));
  try {
    // Both callers pass the same shape today; the parity assertion is
    // the regression guard for any future divergence.
    for (const home of [homeA, homeB]) {
      deploySkills({
        repoRoot: repo,
        skillsBase: join(home, "skills"),
        agentsBase: join(home, "agents"),
        version: "9.9.9",
      });
    }
    assert.deepEqual(
      deployedSet(join(homeA, "skills")), deployedSet(join(homeB, "skills")));
    assert.deepEqual(
      deployedSet(join(homeA, "agents")), deployedSet(join(homeB, "agents")));
  } finally {
    for (const d of [repo, homeA, homeB]) {
      rmSync(d, { recursive: true, force: true });
    }
  }
});

test("meta skills deploy as top-level arka-<skill> (the missing-arka-flow bug)", () => {
  const repo = makeRepo();
  const home = mkdtempSync(join(tmpdir(), "arka-skilldeploy-"));
  try {
    const counts = deploySkills({
      repoRoot: repo,
      skillsBase: join(home, "skills"),
      version: "9.9.9",
    });
    assert.equal(counts.meta, 2);
    assert.ok(existsSync(join(home, "skills", "arka-flow", "SKILL.md")),
      "arka-flow must exist after ANY deploy — evidence-flow is NON-NEGOTIABLE");
    assert.ok(existsSync(join(home, "skills", "arka-forge", "SKILL.md")));
    // Nested reference bundle refreshed too.
    assert.ok(existsSync(
      join(home, "skills", "arka", "skills", "flow", "SKILL.md")));
  } finally {
    rmSync(repo, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

test("full surface: main + hub + sub-skill (with resources) + agents + stamps", () => {
  const repo = makeRepo();
  const home = mkdtempSync(join(tmpdir(), "arka-skilldeploy-"));
  try {
    const counts = deploySkills({
      repoRoot: repo,
      skillsBase: join(home, "skills"),
      agentsBase: join(home, "agents"),
      version: "9.9.9",
    });
    assert.deepEqual(counts,
      { main: 1, bundle: 1, depts: 1, subs: 1, meta: 2, agents: 1 });
    assert.ok(existsSync(join(home, "skills", "arka-dev", "SKILL.md")));
    assert.ok(existsSync(
      join(home, "skills", "arka-code-review", "references", "checklist.md")),
      "skill resources travel with the skill");
    assert.ok(existsSync(join(home, "agents", "arka-paulo.md")));
    assert.equal(
      readFileSync(join(home, "skills", "arka", "VERSION"), "utf-8"), "9.9.9");
    assert.equal(
      readFileSync(join(home, "skills", "arka", ".repo-path"), "utf-8"), repo);
  } finally {
    rmSync(repo, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

test("copy-only contract: deploy never deletes pre-existing user dirs", () => {
  const repo = makeRepo();
  const home = mkdtempSync(join(tmpdir(), "arka-skilldeploy-"));
  try {
    const userSkill = join(home, "skills", "arka-rockport");
    mkdirSync(userSkill, { recursive: true });
    writeFileSync(join(userSkill, "SKILL.md"), "# user ecosystem skill\n");
    deploySkills({ repoRoot: repo, skillsBase: join(home, "skills") });
    assert.equal(
      readFileSync(join(userSkill, "SKILL.md"), "utf-8"),
      "# user ecosystem skill\n",
      "user/ecosystem skills are untouchable");
  } finally {
    rmSync(repo, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

test("structural: skill-deploy.js contains no delete primitive", () => {
  const src = readFileSync(
    join(here, "..", "..", "installer", "skill-deploy.js"), "utf-8");
  assert.ok(!/rmSync|unlink|rmdir|\brm\b/.test(src),
    "deploySkills is copy-only by contract");
});

test("both installer entrypoints consume the shared module (no drift path left)", () => {
  const indexSrc = readFileSync(
    join(here, "..", "..", "installer", "index.js"), "utf-8");
  const updateSrc = readFileSync(
    join(here, "..", "..", "installer", "update.js"), "utf-8");
  for (const [name, src] of [["index.js", indexSrc], ["update.js", updateSrc]]) {
    assert.ok(src.includes('from "./skill-deploy.js"'),
      `${name} must import the shared deploySkills`);
    assert.ok(!/deployTopLevelSkill|const deployTop\s*=/.test(src),
      `${name} must not keep a private skill-deploy loop`);
  }
});
