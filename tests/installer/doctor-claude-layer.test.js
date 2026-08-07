import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import {
  checks,
  checkSkipReason,
  hooksWired,
  statuslineConfigured,
  gotchasHealthy,
  mcpRegistryHealthy,
  deployedSkillCount,
  qgAgentsRepaired,
  qgLedgerPopulated,
} from "../../installer/doctor.js";
import { IS_WINDOWS } from "../../installer/platform.js";

// Claude-layer checks migrated from the retired bash doctor (issue
// #358). The bash side had a bats lock on 18; the node doctor never had
// a count lock at all — this file adds one so a silently dropped or
// duplicated check fails the suite instead of shipping.

const CLAUDE_LAYER_CHECKS = [
  "claude-cli",
  "arka-skill",
  "jq",
  "statusline",
  "hooks-wired",
  "skills-deployed",
  "mcp-registry",
  "watch-media-tooling",
  "gotchas",
  "companion-plugins",
];

// 26 pre-#358 POSIX checks + 10 migrated Claude-layer + 1 autoupdate
// (Foundation PR-1) + 4 install-profile checks (Foundation PR-4:
// install-profile, litellm-proxy, whisper, ollama-execution-model) +
// 1 menubar (Foundation PR-5) + 1 root-consistency (repair PR-A2) +
// 2 Quality Gate checks (repair PR-B5: qg-agents, qg-ledger);
// Windows appends 4.
const EXPECTED_TOTAL = 45 + (IS_WINDOWS ? 4 : 0);

const byName = Object.fromEntries(checks.map((c) => [c.name, c]));

test("doctor check count is locked", () => {
  assert.equal(
    checks.length,
    EXPECTED_TOTAL,
    `doctor has ${checks.length} checks, lock expects ${EXPECTED_TOTAL} — ` +
      "update this lock deliberately when adding/removing a check"
  );
});

test("doctor check names are unique", () => {
  const names = checks.map((c) => c.name);
  assert.equal(new Set(names).size, names.length, "duplicate check name");
});

test("all migrated Claude-layer checks are registered", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    assert.ok(byName[name], `missing doctor check: ${name}`);
  }
});

test("Claude-layer checks are warn-only (multi-runtime installs must not fail)", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    assert.equal(byName[name].severity, "warn", `${name} must be warn`);
  }
});

test("Claude-layer checks run without throwing and return boolean", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    const result = byName[name].check();
    assert.equal(typeof result, "boolean", `${name}.check() must be boolean`);
  }
});

test("Claude-layer fixes are instructions, not installers", () => {
  for (const name of CLAUDE_LAYER_CHECKS) {
    const fix = byName[name].fix();
    assert.equal(typeof fix, "string");
    assert.ok(fix.length > 10, `${name}.fix() must instruct the operator`);
  }
});

// ─── hooksWired — the governance-live gap the bash doctor covered and
// the node hooks-dir check (files on disk) never did.

test("hooksWired: no settings.json means not applicable (true)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    assert.equal(hooksWired(join(dir, "settings.json")), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: settings without hooks is unwired (false)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(p, JSON.stringify({ statusLine: {} }));
    assert.equal(hooksWired(p), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: UserPromptSubmit wiring flips it to true", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(
      p,
      JSON.stringify({ hooks: { UserPromptSubmit: [{ hooks: [] }] } })
    );
    assert.equal(hooksWired(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("hooksWired: corrupt settings.json is unverifiable, surfaced as false", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-hw-"));
  try {
    const p = join(dir, "settings.json");
    writeFileSync(p, "{not json");
    assert.equal(hooksWired(p), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── statuslineConfigured

test("statuslineConfigured: command must point at an existing file", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sl-"));
  try {
    const p = join(dir, "settings.json");
    const cmd = join(dir, "statusline.sh");
    writeFileSync(p, JSON.stringify({ statusLine: { command: cmd } }));
    assert.equal(statuslineConfigured(p), false, "dangling command must fail");
    writeFileSync(cmd, "#!/bin/bash\n");
    assert.equal(statuslineConfigured(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("statuslineConfigured: no settings.json means not applicable (true)", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sl-"));
  try {
    assert.equal(statuslineConfigured(join(dir, "settings.json")), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── gotchasHealthy — live v2 state (/arka evolve ingests it)

test("gotchasHealthy: missing, corrupt, non-array, and valid states", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-gt-"));
  try {
    const p = join(dir, "gotchas.json");
    assert.equal(gotchasHealthy(p), false, "missing must be false");
    writeFileSync(p, "{broken");
    assert.equal(gotchasHealthy(p), false, "corrupt must be false");
    writeFileSync(p, JSON.stringify({ not: "an array" }));
    assert.equal(gotchasHealthy(p), false, "non-array must be false");
    writeFileSync(p, "[]");
    assert.equal(gotchasHealthy(p), true, "empty array is healthy");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── mcpRegistryHealthy

test("mcpRegistryHealthy: requires parseable JSON with mcpServers", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-mr-"));
  try {
    const p = join(dir, "registry.json");
    assert.equal(mcpRegistryHealthy(p), false, "missing must be false");
    writeFileSync(p, "{broken");
    assert.equal(mcpRegistryHealthy(p), false, "corrupt must be false");
    writeFileSync(p, JSON.stringify({ mcpServers: {} }));
    assert.equal(mcpRegistryHealthy(p), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── deployedSkillCount

test("deployedSkillCount: counts only arka-* dirs holding a SKILL.md", () => {
  const dir = mkdtempSync(join(tmpdir(), "arka-sd-"));
  try {
    assert.equal(deployedSkillCount(dir), 0);
    mkdirSync(join(dir, "arka-dev"), { recursive: true });
    assert.equal(deployedSkillCount(dir), 0, "dir without SKILL.md must not count");
    writeFileSync(join(dir, "arka-dev", "SKILL.md"), "# dev\n");
    mkdirSync(join(dir, "unrelated"), { recursive: true });
    writeFileSync(join(dir, "unrelated", "SKILL.md"), "# other\n");
    assert.equal(deployedSkillCount(dir), 1, "non arka-* dirs must not count");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ─── root-consistency (repair PR-A2) ────────────────────────────────────

test("root-consistency: split root warns, same-root spellings pass", () => {
  const entry = byName["root-consistency"];
  assert.ok(entry, "missing doctor check: root-consistency");
  assert.equal(entry.severity, "warn", "advisory, never fails the install");
  assert.ok(entry.fix().includes("shell rc"), "fix must say where to remove it");

  const saved = process.env.ARKAOS_ROOT;
  try {
    delete process.env.ARKAOS_ROOT;
    assert.equal(entry.check(), true, "no override => one root, consistent");
    process.env.ARKAOS_ROOT = join(homedir(), ".arkaos", "lib") + "/";
    assert.equal(
      entry.check(), true,
      "a trailing slash on the snapshot names the same root"
    );
    process.env.ARKAOS_ROOT = join(tmpdir(), "somewhere-else-entirely");
    assert.equal(entry.check(), false, "an unrelated override is a split root");
  } finally {
    if (saved === undefined) delete process.env.ARKAOS_ROOT;
    else process.env.ARKAOS_ROOT = saved;
  }
});

// ─── Quality Gate checks (repair PR-B5) ─────────────────────────────────

test("qg-agents: shape, project scoping, and repair matrix", () => {
  const entry = byName["qg-agents"];
  assert.ok(entry, "missing doctor check: qg-agents");
  assert.equal(entry.severity, "fail", "an unrepaired project is a broken relay");
  // QG r2 (both reviewers independently): the check fails on TWO
  // scopes and each needs its own command — init reaches only the
  // project (deployProjectAgents); the user-scope retirement runs in
  // deploySkills, reached from update. A fix naming init alone is a
  // dead-end loop.
  assert.ok(entry.fix().includes("npx arkaos update"),
    "fix must name the command that clears the user scope");
  assert.ok(entry.fix().includes("npx arkaos init"),
    "fix must name the command that deploys the project reviewers");
  assert.match(entry.description, /user scope/,
    "description must say the check spans user scope");

  const dir = mkdtempSync(join(tmpdir(), "arkaos-qg-agents-"));
  try {
    const agentsDir = join(dir, ".claude", "agents");
    // Injected empty user scope: the default points at the REAL
    // ~/.claude/agents, which may legitimately carry v1 personas on a
    // not-yet-updated machine — a unit test must not depend on it.
    const userDir = join(dir, "user-agents");
    mkdirSync(userDir, { recursive: true });

    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), false,
      "no agents dir at all => not repaired"
    );

    mkdirSync(agentsDir, { recursive: true });
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), false,
      "reviewers absent => fail"
    );

    for (const r of ["marta-cqo", "eduardo-copy", "francisca-tech"]) {
      writeFileSync(join(agentsDir, `${r}.md`), "contract with QGVerdict\n");
    }
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), true,
      "three contracted reviewers => repaired"
    );

    writeFileSync(join(agentsDir, "cqo.md"), "v1 persona\n");
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), false,
      "a dispatchable v1 persona => not repaired"
    );
    rmSync(join(agentsDir, "cqo.md"));

    writeFileSync(join(agentsDir, "francisca-tech.md"), "no contract here\n");
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), false,
      "a reviewer without the QGVerdict contract => not repaired"
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("qg-agents: user-scope v1 QG personas fail the check by frontmatter name", () => {
  // QG r1 B2: the installer used to deploy the v1 trio to
  // ~/.claude/agents/arka-<name>.md — the arka- prefix defeats
  // basename matching, so detection reads the frontmatter name.
  const dir = mkdtempSync(join(tmpdir(), "arkaos-qg-userscope-"));
  try {
    const agentsDir = join(dir, ".claude", "agents");
    const userDir = join(dir, "user-agents");
    mkdirSync(agentsDir, { recursive: true });
    mkdirSync(userDir, { recursive: true });
    for (const r of ["marta-cqo", "eduardo-copy", "francisca-tech"]) {
      writeFileSync(join(agentsDir, `${r}.md`), "contract with QGVerdict\n");
    }

    writeFileSync(
      join(userDir, "arka-cqo.md"),
      "---\nname: cqo\ndescription: v1 persona\n---\nbody\n"
    );
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), false,
      "a user-scope v1 QG persona keeps the relay broken"
    );

    rmSync(join(userDir, "arka-cqo.md"));
    writeFileSync(
      join(userDir, "arka-paulo.md"),
      "---\nname: paulo-tech-lead\n---\nbody\n"
    );
    assert.equal(
      qgAgentsRepaired(agentsDir, userDir), true,
      "non-QG user agents never trip the check"
    );

    rmSync(dir, { recursive: true, force: true });
    assert.equal(
      qgAgentsRepaired(agentsDir, join(dir, "missing")), false,
      "missing project dir still fails regardless of user scope"
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("checkSkipReason: a throwing skipIf never hides its check", () => {
  // QG r1 M2: the catch arm was untested — a broken predicate must
  // run the check normally, not skip it (and not crash the doctor).
  const entry = {
    name: "fake",
    skipIf: () => {
      throw new Error("broken predicate");
    },
  };
  assert.equal(checkSkipReason(entry, "essential"), null);
});

test("qg-agents: skipIf makes it an informational skip outside a project", () => {
  const entry = byName["qg-agents"];
  const savedCwd = process.cwd();
  const dir = mkdtempSync(join(tmpdir(), "arkaos-qg-skip-"));
  try {
    process.chdir(dir);
    const reason = checkSkipReason(entry, "essential");
    assert.ok(reason, "outside a project the check must skip, not fail");
    assert.match(reason, /run inside a project/);

    mkdirSync(join(dir, ".claude", "agents"), { recursive: true });
    assert.equal(
      checkSkipReason(entry, "essential"), null,
      "inside a project the check applies"
    );
  } finally {
    process.chdir(savedCwd);
    rmSync(dir, { recursive: true, force: true });
  }
});

test("qg-ledger: warn severity, empty/missing root fails, populated passes", () => {
  const entry = byName["qg-ledger"];
  assert.ok(entry, "missing doctor check: qg-ledger");
  assert.equal(
    entry.severity, "warn",
    "a fresh install legitimately starts empty — warn, never fail"
  );

  const dir = mkdtempSync(join(tmpdir(), "arkaos-qg-ledger-"));
  try {
    const root = join(dir, "quality-gate");
    assert.equal(qgLedgerPopulated(root), false, "missing root => channel never exercised");
    mkdirSync(root, { recursive: true });
    assert.equal(qgLedgerPopulated(root), false, "empty root => channel never exercised");
    mkdirSync(join(root, "sess-1"), { recursive: true });
    assert.equal(qgLedgerPopulated(root), true, "a captured session => channel alive");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
