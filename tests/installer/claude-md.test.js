// Tests for installer/claude-md.js (PR-C5 — managed-block CLAUDE.md).
//
// Contract under test, from the approved spec
// .arkaos/specs/installer-claude-md-managed-block.yaml: once the block
// exists, updates only rewrite the marked region; an unmarked file is
// adopted (known template hash or template prefix -> wrap keeping the
// operator remainder, anything else -> prepend; never lose a byte); a
// backup precedes every mutation; deleted markers are respected, not
// re-seeded; malformed markers, non-UTF-8 files and broken symlinks are
// refusals; a rewrite preserves the file mode and fresh files respect
// the umask; fresh installs write the template already wrapped.

import { test } from "node:test";
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import {
  mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync,
  existsSync, rmSync, symlinkSync, lstatSync, statSync, chmodSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const {
  MARKER_START, MARKER_END, KNOWN_TEMPLATE_HASHES, sha256,
  renderManagedBlock, analyzeMarkers, planUpdate, tempPathFor,
  syncUserClaudeMd, installUserClaudeMd, describeSyncResult,
} = await import(join(ROOT, "installer", "claude-md.js"));

const TEMPLATE_PATH = join(ROOT, "config", "user-claude.md");
const TEMPLATE = readFileSync(TEMPLATE_PATH, "utf-8");

// The exact three lines the 2026-08-03 autoupdater incident destroyed
// (spec acceptance criterion 1: they must come back identical).
const GRAPHIFY_BLOCK = [
  "# graphify",
  "- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`",
  'When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.',
].join("\n");

function makeTmpHome() {
  const dir = mkdtempSync(join(tmpdir(), "arkaos-claude-md-test-"));
  return {
    dir,
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function writeUserClaudeMd(home, content) {
  const path = join(home, ".claude", "CLAUDE.md");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content);
  return path;
}

function readUserClaudeMd(home) {
  return readFileSync(join(home, ".claude", "CLAUDE.md"), "utf-8");
}

function listBackups(home) {
  const dir = join(home, ".claude");
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.includes(".arkaos-backup-"));
}

function sync(home) {
  return syncUserClaudeMd({ home, templatePath: TEMPLATE_PATH });
}

// ── Acceptance 1: operator content survives byte-for-byte ────────────

test("incident reproduction: operator remainder survives byte-for-byte, shipped text exactly once", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    // The destroyed file's exact shape: shipped template with the
    // operator's three /graphify lines appended. The template prefix is
    // absorbed into the managed block (prepending would duplicate the
    // whole instruction set — QG C5 r1, Francisca B2); the operator
    // remainder must survive byte-for-byte below it.
    const remainder = `\n${GRAPHIFY_BLOCK}\n`;
    writeUserClaudeMd(dir, `${TEMPLATE}${remainder}`);

    const result = sync(dir);

    assert.equal(result.action, "adopt-wrap");
    const after = readUserClaudeMd(dir);
    assert.equal(after, renderManagedBlock(TEMPLATE) + remainder);
    assert.ok(after.includes(GRAPHIFY_BLOCK), "the /graphify block must come back identical");
    const firstHeading = TEMPLATE.split("\n")[0];
    assert.equal(after.split(firstHeading).length - 1, 1, "shipped text must appear exactly once");
    // The modal path must TELL the operator their content survived —
    // after a data-loss incident, the common path prints the reassurance.
    assert.equal(result.preservedRemainder, true);
    assert.match(describeSyncResult(result).message, /your content preserved below the managed block/);
  } finally {
    cleanup();
  }
});

test("operator-only file (no template prefix) takes adopt-prepend and is preserved below the block", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const operatorFile = "# My own rules\n\nNever touch prod on Fridays.\n";
    writeUserClaudeMd(dir, operatorFile);

    const result = sync(dir);

    assert.equal(result.action, "adopt-prepend");
    const after = readUserClaudeMd(dir);
    assert.ok(after.endsWith(operatorFile));
    const firstHeading = TEMPLATE.split("\n")[0];
    assert.equal(after.split(firstHeading).length - 1, 1, "shipped text must appear exactly once");
  } finally {
    cleanup();
  }
});

// ── Non-UTF-8 files are refusals, never silent corruption ────────────

const LATIN1_UNMARKED = Buffer.from("# Regras do Andr\xe9\n", "latin1");
const LATIN1_MARKED = Buffer.concat([
  Buffer.from(`${MARKER_START}\nx\n${MARKER_END}\n`, "utf-8"),
  Buffer.from("N\xe3o toques na produ\xe7\xe3o\n", "latin1"),
]);

for (const [label, bytes] of [["unmarked", LATIN1_UNMARKED], ["with markers", LATIN1_MARKED]]) {
  test(`non-UTF-8 file (${label}) -> refusal, bytes untouched`, () => {
    const { dir, cleanup } = makeTmpHome();
    try {
      const path = join(dir, ".claude", "CLAUDE.md");
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, bytes);

      const result = sync(dir);

      assert.equal(result.action, "refuse");
      assert.match(result.reason, /UTF-8/);
      assert.ok(readFileSync(path).equals(bytes), "no byte may change on refusal");
      assert.equal(listBackups(dir).length, 0);
    } finally {
      cleanup();
    }
  });
}

// ── Acceptance 2: known template hash -> wrap, no duplication ────────

test("file matching the shipped template hash is wrapped in markers with no duplication", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    writeUserClaudeMd(dir, TEMPLATE);

    const result = sync(dir);

    assert.equal(result.action, "adopt-wrap");
    const after = readUserClaudeMd(dir);
    assert.equal(after, renderManagedBlock(TEMPLATE));
    const firstHeading = TEMPLATE.split("\n")[0];
    assert.equal(after.split(firstHeading).length - 1, 1, "template text must appear exactly once");
  } finally {
    cleanup();
  }
});

// ── Acceptance 3: idempotency ────────────────────────────────────────

test("running the update twice is byte-identical with a single marker pair and no second backup", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    writeUserClaudeMd(dir, `${TEMPLATE}\n${GRAPHIFY_BLOCK}\n`);

    sync(dir);
    const afterFirst = readUserClaudeMd(dir);
    const second = sync(dir);
    const afterSecond = readUserClaudeMd(dir);

    assert.equal(second.action, "unchanged");
    assert.equal(afterSecond, afterFirst);
    assert.equal(afterSecond.split(MARKER_START).length - 1, 1);
    assert.equal(afterSecond.split(MARKER_END).length - 1, 1);
    assert.equal(listBackups(dir).length, 1, "an unchanged run must not add a backup");
  } finally {
    cleanup();
  }
});

// ── Acceptance 4: deleted markers are respected, never re-seeded ─────

test("markers deleted by the operator after adoption -> no write, no re-seed", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    writeUserClaudeMd(dir, TEMPLATE);
    sync(dir); // adopts; records managed state

    const operatorOnly = "# Deliberately unmanaged\n";
    writeUserClaudeMd(dir, operatorOnly);
    const backupsBefore = listBackups(dir).length;

    const result = sync(dir);

    assert.equal(result.action, "markers-removed");
    assert.equal(readUserClaudeMd(dir), operatorOnly, "the file must be left untouched");
    assert.equal(listBackups(dir).length, backupsBefore);
    assert.equal(describeSyncResult(result).level, "warn");
  } finally {
    cleanup();
  }
});

// ── Acceptance 5: backup before any mutation ─────────────────────────

test("a backup with the pre-update bytes exists and its path is reported", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const before = `${TEMPLATE}\n${GRAPHIFY_BLOCK}\n`;
    writeUserClaudeMd(dir, before);

    const result = sync(dir);

    assert.ok(result.backupPath, "mutations must report the backup path");
    assert.ok(existsSync(result.backupPath));
    assert.equal(readFileSync(result.backupPath, "utf-8"), before, "backup must restore the pre-update file byte-for-byte");
    assert.ok(describeSyncResult(result).detail.includes(result.backupPath));
  } finally {
    cleanup();
  }
});

test("creating a missing file needs no backup", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = sync(dir);
    assert.equal(result.action, "created");
    assert.equal(result.backupPath, null);
    assert.equal(readUserClaudeMd(dir), renderManagedBlock(TEMPLATE));
  } finally {
    cleanup();
  }
});

// ── Acceptance 6: malformed markers are refusals, never writes ───────

const MALFORMED_CASES = [
  ["start without end", `${MARKER_START}\ncontent\n`],
  ["end without start", `content\n${MARKER_END}\n`],
  ["two marker pairs", `${MARKER_START}\na\n${MARKER_END}\n${MARKER_START}\nb\n${MARKER_END}\n`],
  ["inverted order", `${MARKER_END}\ncontent\n${MARKER_START}\n`],
];

for (const [label, content] of MALFORMED_CASES) {
  test(`malformed markers (${label}) -> refusal with a reason, file untouched`, () => {
    const { dir, cleanup } = makeTmpHome();
    try {
      writeUserClaudeMd(dir, content);

      const result = sync(dir);

      assert.equal(result.action, "refuse");
      assert.ok(result.reason, "a refusal must carry a reason");
      assert.equal(readUserClaudeMd(dir), content);
      assert.equal(listBackups(dir).length, 0);
      assert.equal(describeSyncResult(result).level, "warn");
    } finally {
      cleanup();
    }
  });
}

// ── Managed-block surgery: bytes outside the block are never touched ─

test("content above and below an existing block survives a template change untouched", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const prefix = "operator prefix line\n";
    const suffix = "\noperator suffix line\n";
    writeUserClaudeMd(dir, `${prefix}${MARKER_START}\nstale shipped text\n${MARKER_END}${suffix}`);

    const result = sync(dir);

    assert.equal(result.action, "replace-block");
    const after = readUserClaudeMd(dir);
    assert.ok(after.startsWith(prefix));
    assert.ok(after.endsWith(suffix));
    assert.ok(after.includes(TEMPLATE.trimEnd()));
    assert.ok(!after.includes("stale shipped text"));
  } finally {
    cleanup();
  }
});

test("corrupt managed-state degrades to adoption, which loses nothing", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const operatorFile = "# Mine\n";
    writeUserClaudeMd(dir, operatorFile);
    const statePath = join(dir, ".arkaos", "claude-md-state.json");
    mkdirSync(dirname(statePath), { recursive: true });
    writeFileSync(statePath, "{not json");

    const result = sync(dir);

    assert.equal(result.action, "adopt-prepend");
    assert.ok(readUserClaudeMd(dir).endsWith(operatorFile));
  } finally {
    cleanup();
  }
});

// ── Acceptance 7: fresh install writes markers, preserve unchanged ───

test("fresh install writes the template wrapped in markers", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const result = installUserClaudeMd({ home: dir, templatePath: TEMPLATE_PATH });

    assert.equal(result.action, "created");
    assert.equal(readUserClaudeMd(dir), renderManagedBlock(TEMPLATE));
  } finally {
    cleanup();
  }
});

test("fresh install preserves an existing file byte-for-byte", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const existing = "operator file, no markers\n";
    writeUserClaudeMd(dir, existing);

    const result = installUserClaudeMd({ home: dir, templatePath: TEMPLATE_PATH });

    assert.equal(result.action, "preserved");
    assert.equal(readUserClaudeMd(dir), existing);
    assert.equal(describeSyncResult(result).message, "~/.claude/CLAUDE.md already exists (preserved)");
  } finally {
    cleanup();
  }
});

// ── Known-hash set is derived, and locked against template drift ─────

test("the current tracked template hashes into KNOWN_TEMPLATE_HASHES", () => {
  assert.ok(
    KNOWN_TEMPLATE_HASHES.includes(sha256(TEMPLATE)),
    "config/user-claude.md changed — add its sha256 to KNOWN_TEMPLATE_HASHES in installer/claude-md.js",
  );
});

test("every git revision of the template is in KNOWN_TEMPLATE_HASHES", (t) => {
  let revs;
  try {
    revs = execSync("git log --follow --format=%H -- config/user-claude.md", {
      cwd: ROOT, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"],
    }).trim().split("\n").filter(Boolean);
  } catch {
    t.diagnostic("git history unavailable — current-file hash lock still applies");
    return;
  }
  for (const rev of revs) {
    let content;
    try {
      content = execSync(`git show ${rev}:config/user-claude.md`, {
        cwd: ROOT, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"],
      });
    } catch {
      continue; // shallow clone: revision listed but object unavailable
    }
    assert.ok(
      KNOWN_TEMPLATE_HASHES.includes(sha256(content)),
      `template revision ${rev} is missing from KNOWN_TEMPLATE_HASHES`,
    );
  }
});

// ── Atomic writes and symlinked files ────────────────────────────────

test("a symlinked CLAUDE.md is written through to its target, the link survives", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const realFile = join(dir, "dotfiles-CLAUDE.md");
    writeFileSync(realFile, "# My own rules\n");
    const link = join(dir, ".claude", "CLAUDE.md");
    mkdirSync(dirname(link), { recursive: true });
    symlinkSync(realFile, link);

    const result = sync(dir);

    assert.equal(result.action, "adopt-prepend");
    assert.ok(lstatSync(link).isSymbolicLink(), "the link itself must survive the write");
    assert.ok(readFileSync(realFile, "utf-8").endsWith("# My own rules\n"),
      "the write must land on the symlink target");
  } finally {
    cleanup();
  }
});

test("a broken symlink at the target is a refusal — the link is never replaced (M3)", () => {
  // existsSync follows links, so a dangling link reads as "no file";
  // before the guard the create path replaced the LINK with a regular
  // file. Both entry points must refuse and leave the link untouched.
  const { dir, cleanup } = makeTmpHome();
  try {
    const target = join(dir, ".claude", "CLAUDE.md");
    mkdirSync(dirname(target), { recursive: true });
    symlinkSync(join(dir, "does-not-exist.md"), target);

    const updated = sync(dir);
    assert.equal(updated.action, "refuse");
    assert.match(updated.reason, /symlink/);
    assert.ok(lstatSync(target).isSymbolicLink(), "the dangling link must survive the update path");

    const installed = installUserClaudeMd({ home: dir, templatePath: TEMPLATE_PATH });
    assert.equal(installed.action, "refuse");
    assert.ok(lstatSync(target).isSymbolicLink(), "the dangling link must survive the install path");
  } finally {
    cleanup();
  }
});

test("a restrictive file mode survives a managed rewrite — 0600 never widens (M1, CWE-732)", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    const path = writeUserClaudeMd(dir, renderManagedBlock("# Old shipped text\n"));
    chmodSync(path, 0o600);

    const result = sync(dir);

    assert.equal(result.action, "replace-block");
    assert.equal(statSync(path).mode & 0o7777, 0o600);
  } finally {
    cleanup();
  }
});

test("a freshly created CLAUDE.md respects the operator's umask, like master's plain write (M1)", () => {
  // umask-relative on purpose: asserting a literal 0644 locked in a
  // widening for umask-077 operators (QG r1, Francisca B1). The
  // sibling is written by a plain writeFileSync — the master baseline.
  // The umask is forced to 077 for the duration so a hard-coded mode
  // diverges from the baseline regardless of the ambient umask — at
  // the CI default 022 a faithful reintroduction of the widening
  // passed all tests (QG r2, Francisca A1, mutant M7).
  const { dir, cleanup } = makeTmpHome();
  const prevUmask = process.umask(0o077);
  try {
    const result = installUserClaudeMd({ home: dir, templatePath: TEMPLATE_PATH });

    assert.equal(result.action, "created");
    const sibling = join(dir, "umask-sibling");
    writeFileSync(sibling, "baseline");
    assert.equal(
      statSync(join(dir, ".claude", "CLAUDE.md")).mode & 0o7777,
      statSync(sibling).mode & 0o7777,
    );
  } finally {
    process.umask(prevUmask);
    cleanup();
  }
});

test("atomic-write invariants hidden by the rename or by the ambient umask are source-pinned", () => {
  // After renameSync neither the replace-path temp's 0600 nor the
  // chmod-before-rename ordering can be observed (QG r1 mutants 3+4
  // survived every behavioural test). The third pin holds the fresh
  // branch to a bare two-argument write — the spec criterion "never a
  // hard-coded mode" enforced at the source (QG r2, Eduardo + Francisca
  // A1). These pins fail safe — a false red on a refactor, never a
  // false green.
  const src = readFileSync(join(ROOT, "installer", "claude-md.js"), "utf-8");
  assert.match(src, /writeFileSync\(tmp, content, \{ mode: 0o600 \}\)/);
  assert.match(src, /chmodSync\(tmp, existingMode\)/);
  assert.match(src, /if \(existingMode === null\) \{\s*writeFileSync\(tmp, content\);/);
});

test("no temp file is left behind after a sync", () => {
  const { dir, cleanup } = makeTmpHome();
  try {
    writeUserClaudeMd(dir, "# Mine\n");
    sync(dir);
    const leftovers = readdirSync(join(dir, ".claude")).filter((f) => f.includes("arkaos-tmp"));
    assert.deepEqual(leftovers, []);
  } finally {
    cleanup();
  }
});

test("atomic temp names are PID-scoped so concurrent processes cannot collide", () => {
  // Behavioural half: two pids must yield two names, and the default
  // pid is the current process. The name is unobservable after the
  // rename, so a minimal source pin still holds writeAtomic to USING
  // the helper — without it a mutant could inline a fixed temp name.
  assert.notEqual(tempPathFor("/h/CLAUDE.md", 111), tempPathFor("/h/CLAUDE.md", 222));
  assert.equal(tempPathFor("/h/CLAUDE.md"), tempPathFor("/h/CLAUDE.md", process.pid));
  const src = readFileSync(join(ROOT, "installer", "claude-md.js"), "utf-8");
  assert.match(src, /const tmp = tempPathFor\(real\)/);
});

test("describeSyncResult falls back to a warning on an unknown action", () => {
  const described = describeSyncResult({ action: "bogus-action" });
  assert.equal(described.level, "warn");
  assert.ok(described.message.includes("bogus-action"));
});

// ── Pure helpers ─────────────────────────────────────────────────────

test("analyzeMarkers classifies all marker states", () => {
  assert.equal(analyzeMarkers("no markers here").state, "none");
  assert.equal(analyzeMarkers(renderManagedBlock("x")).state, "ok");
  for (const [, content] of MALFORMED_CASES) {
    assert.equal(analyzeMarkers(content).state, "malformed");
  }
});

test("a file equal to an OLD template revision wraps via the hash gate, not the prefix match", () => {
  // Future shape: the template has been revised, an untouched install
  // still carries the old revision verbatim. It no longer prefix-matches
  // the current template, so only the known-hash gate can say "ours".
  const oldRevision = "# ArkaOS — User Instructions (old revision)\n";
  assert.ok(!oldRevision.startsWith(TEMPLATE));
  const plan = planUpdate({
    existing: oldRevision,
    template: TEMPLATE,
    wasManaged: false,
    knownHashes: [sha256(oldRevision)],
  });
  assert.equal(plan.action, "adopt-wrap");
  assert.equal(plan.content, renderManagedBlock(TEMPLATE));
});

test("planUpdate never returns a content-bearing action for refusals or removed markers", () => {
  const refused = planUpdate({ existing: `${MARKER_START}\n`, template: TEMPLATE, wasManaged: false });
  assert.equal(refused.action, "refuse");
  assert.equal(refused.content, undefined);

  const removed = planUpdate({ existing: "bare file\n", template: TEMPLATE, wasManaged: true });
  assert.equal(removed.action, "markers-removed");
  assert.equal(removed.content, undefined);
});

// ── Wiring pins: the destructive copy is gone from both callers ──────

test("update.js routes CLAUDE.md through syncUserClaudeMd and no longer blind-copies it", () => {
  const src = readFileSync(join(ROOT, "installer", "update.js"), "utf-8");
  assert.ok(src.includes("syncUserClaudeMd("), "update.js must call the managed-block sync");
  assert.ok(!src.includes("copyFileSync(claudeMdSrc"), "the destructive copy must not come back");
});

test("index.js routes CLAUDE.md through installUserClaudeMd", () => {
  const src = readFileSync(join(ROOT, "installer", "index.js"), "utf-8");
  assert.ok(src.includes("installUserClaudeMd("), "index.js must call the managed-block install");
  assert.ok(!src.includes("copyFileSync(claudeMdSrc"), "the raw template copy must not come back");
});
