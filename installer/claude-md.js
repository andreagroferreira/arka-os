// Managed-block writer for ~/.claude/CLAUDE.md (PR-C5).
//
// installer/update.js used to copy the packaged template straight over
// the live file. On 2026-08-03 the launchd autoupdater did exactly that
// and destroyed the operator's own instructions (spec
// .arkaos/specs/installer-claude-md-managed-block.yaml, incident on
// record). The contract now: shipped instructions live inside an
// explicitly marked region; once the block exists only that region is
// rewritten, an unmarked file is adopted (wrapped or prepended to), and
// no operator byte is ever lost.
//
// An unmarked existing file is ambiguous between "pre-C5 install we
// should adopt" and "the operator deleted our markers on purpose".
// Those demand OPPOSITE actions (adopt vs leave alone), so adoption is
// recorded in ~/.arkaos/claude-md-state.json; a missing or unreadable
// state degrades to adoption, which loses no operator byte.

import { createHash } from "node:crypto";
import {
  chmodSync, copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync,
  realpathSync, renameSync, statSync, writeFileSync,
} from "node:fs";
import { join, dirname } from "node:path";

export const MARKER_START = "<!-- arka:user-instructions:start -->";
export const MARKER_END = "<!-- arka:user-instructions:end -->";

// Every revision of config/user-claude.md ever shipped, by sha256 of its
// exact bytes. An unmarked file matching one of these is ours to wrap;
// anything else carries operator edits and is preserved — a file that
// starts with the shipped template keeps only its remainder below the
// block; every other file is prepended to.
// tests/installer/claude-md.test.js fails when the tracked template
// changes without this list growing.
export const KNOWN_TEMPLATE_HASHES = Object.freeze([
  // config/user-claude.md @ 05ce86e2 (2026-04-08), sole revision to date
  "cf7c007c9568fe3edc40877e9ce526fc4edaf7c458c0ae6e0e92354b229709a0",
]);

export function sha256(text) {
  return createHash("sha256").update(text, "utf-8").digest("hex");
}

export function renderManagedBlock(template) {
  const body = template.endsWith("\n") ? template : `${template}\n`;
  return `${MARKER_START}\n${body}${MARKER_END}\n`;
}

// Marker states: "none" (no marker at all), "ok" (exactly one
// well-ordered pair), "malformed" (anything else, with a reason).
// Malformed is always a refusal upstream — a wrong guess about which
// bytes are ours is how content gets destroyed.
export function analyzeMarkers(content) {
  const starts = indexesOf(content, MARKER_START);
  const ends = indexesOf(content, MARKER_END);
  if (starts.length === 0 && ends.length === 0) return { state: "none" };
  if (starts.length === 0) return malformed("end marker without a start marker");
  if (ends.length === 0) return malformed("start marker without an end marker");
  if (starts.length > 1 || ends.length > 1) {
    return malformed("more than one managed block marker pair");
  }
  if (ends[0] < starts[0]) return malformed("end marker appears before the start marker");
  return { state: "ok", start: starts[0], end: ends[0] + MARKER_END.length };
}

function malformed(reason) {
  return { state: "malformed", reason };
}

function indexesOf(content, needle) {
  const found = [];
  let at = content.indexOf(needle);
  while (at !== -1) {
    found.push(at);
    at = content.indexOf(needle, at + needle.length);
  }
  return found;
}

// Pure decision. `existing` is the current file content (null when the
// file does not exist); `wasManaged` is the recorded adoption state.
// `knownHashes` is injectable because the shipped list's discriminating
// entries are OLD template revisions — files exactly equal to one must
// wrap, not prepend, even though they no longer prefix-match the
// current template. With a single shipped revision that case cannot be
// built from the real list, so the tests pin it with a synthetic one.
export function planUpdate({ existing, template, wasManaged, knownHashes = KNOWN_TEMPLATE_HASHES }) {
  if (existing === null) return { action: "created", content: renderManagedBlock(template) };
  const markers = analyzeMarkers(existing);
  if (markers.state === "malformed") return { action: "refuse", reason: markers.reason };
  if (markers.state === "ok") return planBlockReplace(existing, template, markers);
  if (wasManaged) return { action: "markers-removed" };
  if (knownHashes.includes(sha256(existing))) {
    return { action: "adopt-wrap", content: renderManagedBlock(template) };
  }
  // "Shipped template + operator additions" is the MODAL pre-C5 shape —
  // every existing install was blind-copied from this same template and
  // then edited below it. Prepending here would duplicate the entire
  // instruction set (QG C5 r1, Francisca B2 — reproduced on the
  // operator's live file), so the template prefix is absorbed into the
  // block and only the operator's remainder is preserved below it.
  if (existing.startsWith(template)) {
    return {
      action: "adopt-wrap",
      content: renderManagedBlock(template) + existing.slice(template.length),
      preservedRemainder: existing.length > template.length,
    };
  }
  return { action: "adopt-prepend", content: `${renderManagedBlock(template)}\n${existing}` };
}

function planBlockReplace(existing, template, markers) {
  const block = renderManagedBlock(template);
  // The rendered block ends with "\n"; when the marker pair is mid-file
  // the original suffix already carries whatever followed the end
  // marker, so the block is spliced in without its trailing newline.
  const spliced = block.slice(0, -1);
  const content =
    existing.slice(0, markers.start) + spliced + existing.slice(markers.end);
  if (content === existing) return { action: "unchanged" };
  return { action: "replace-block", content };
}

// Temp names are PID-scoped so concurrent processes cannot collide on
// the same temp path. Exported so the tests can assert the scoping
// behaviourally — the name is unobservable after the rename.
export function tempPathFor(real, pid = process.pid) {
  return `${real}.arkaos-tmp-${pid}`;
}

// A crash mid-write must never leave a truncated CLAUDE.md, and a
// symlinked file must keep pointing at its target — renaming onto the
// LINK would replace the link itself (the C3 remediation lesson), so
// the write lands on the resolved path. Known trade-off of temp+rename:
// a HARD-linked twin keeps the old inode's content.
// The rename carries the temp file's mode with it. When a file is
// being REPLACED, the temp starts at 0600 (never readable by group or
// other) and is chmod-ed to the existing file's mode before the rename
// — a 0600 CLAUDE.md must not come back 0644 (CWE-732, C5 register
// M1). A FRESH file is written plainly so the operator's umask applies
// exactly as master's writeFileSync did — a hard-coded 0644 here
// WIDENED a umask-077 operator's file (QG r1, Francisca B1).
function writeAtomic(target, content) {
  const real = existsSync(target) ? realpathSync(target) : target;
  const existingMode = existsSync(real) ? statSync(real).mode & 0o7777 : null;
  const tmp = tempPathFor(real);
  if (existingMode === null) {
    writeFileSync(tmp, content);
  } else {
    writeFileSync(tmp, content, { mode: 0o600 });
    chmodSync(tmp, existingMode);
  }
  renameSync(tmp, real);
}

// existsSync FOLLOWS symlinks, so a dangling link reads as "no file
// here" and the create path would silently replace the link itself
// with a regular file (C5 register M3). lstat sees the link; refuse
// and leave it exactly as found.
function brokenSymlinkReason(target) {
  let stat;
  try {
    stat = lstatSync(target);
  } catch {
    return null;
  }
  if (stat.isSymbolicLink() && !existsSync(target)) {
    return "it is a symlink whose target does not exist — fix or remove the link first";
  }
  return null;
}

export function backupFile(target) {
  const stamp = new Date().toISOString().replace(/[-:.]/g, "");
  let dest = `${target}.arkaos-backup-${stamp}`;
  let n = 1;
  while (existsSync(dest)) dest = `${target}.arkaos-backup-${stamp}-${n++}`;
  copyFileSync(target, dest);
  return dest;
}

function statePath(home) {
  return join(home, ".arkaos", "claude-md-state.json");
}

function readManagedState(home) {
  try {
    return JSON.parse(readFileSync(statePath(home), "utf-8")).managed === true;
  } catch {
    return false;
  }
}

function writeManagedState(home, lastAction) {
  const path = statePath(home);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify({ managed: true, lastAction }, null, 2)}\n`);
}

// Update path (installer/update.js). Reads, decides, backs up before
// any mutation of an existing file, writes, records adoption. CLAUDE.md
// itself is never touched on refuse/markers-removed/unchanged (the
// unchanged path still records the adoption state).
export function syncUserClaudeMd({ home, templatePath }) {
  if (!existsSync(templatePath)) return { action: "no-template" };
  const template = readFileSync(templatePath, "utf-8");
  const target = join(home, ".claude", "CLAUDE.md");
  const brokenLink = brokenSymlinkReason(target);
  if (brokenLink) return { action: "refuse", reason: brokenLink };
  const raw = existsSync(target) ? readFileSync(target) : null;
  // Decoding a non-UTF-8 file replaces bytes with U+FFFD and writing
  // the decode back corrupts content OUTSIDE the block (QG C5 r1,
  // Francisca B1 — reproduced on latin-1). Refuse unless it round-trips.
  if (raw !== null && !Buffer.from(raw.toString("utf-8"), "utf-8").equals(raw)) {
    return { action: "refuse", reason: "file is not valid UTF-8 — a rewrite would corrupt it" };
  }
  const existing = raw === null ? null : raw.toString("utf-8");
  const plan = planUpdate({ existing, template, wasManaged: readManagedState(home) });

  if (plan.action === "refuse" || plan.action === "markers-removed") return plan;
  if (plan.action === "unchanged") {
    writeManagedState(home, plan.action);
    return plan;
  }
  const backupPath = existing === null ? null : backupFile(target);
  mkdirSync(dirname(target), { recursive: true });
  writeAtomic(target, plan.content);
  writeManagedState(home, plan.action);
  const result = { action: plan.action, backupPath, path: target };
  if (plan.preservedRemainder) result.preservedRemainder = true;
  return result;
}

// Fresh-install path (installer/index.js). Only ever writes when the
// file does not exist — the historical "already exists (preserved)"
// behaviour is unchanged; adoption belongs to the update path.
export function installUserClaudeMd({ home, templatePath }) {
  if (!existsSync(templatePath)) return { action: "no-template" };
  const target = join(home, ".claude", "CLAUDE.md");
  const brokenLink = brokenSymlinkReason(target);
  if (brokenLink) return { action: "refuse", reason: brokenLink };
  if (existsSync(target)) return { action: "preserved" };
  mkdirSync(dirname(target), { recursive: true });
  writeAtomic(target, renderManagedBlock(readFileSync(templatePath, "utf-8")));
  writeManagedState(home, "created");
  return { action: "created", path: target };
}

// One printable line per outcome so update.js and index.js report the
// same result the same way.
export function describeSyncResult(result) {
  const messages = {
    "no-template": { level: "warn", message: "CLAUDE.md template missing from package — skipped" },
    refuse: { level: "warn", message: `~/.claude/CLAUDE.md NOT updated: ${result.reason}` },
    "markers-removed": {
      level: "warn",
      message: "~/.claude/CLAUDE.md managed markers were removed — treated as deliberate; file left untouched",
    },
    unchanged: { level: "ok", message: "~/.claude/CLAUDE.md already up to date" },
    preserved: { level: "ok", message: "~/.claude/CLAUDE.md already exists (preserved)" },
    created: { level: "ok", message: "~/.claude/CLAUDE.md created (ArkaOS user instructions)" },
    "replace-block": {
      level: "ok",
      message: "~/.claude/CLAUDE.md updated inside the arka:user-instructions markers only",
    },
    "adopt-wrap": {
      level: "ok",
      message: result.preservedRemainder
        ? "~/.claude/CLAUDE.md adopted into managed markers — your content preserved below the managed block"
        : "~/.claude/CLAUDE.md adopted into managed markers",
    },
    "adopt-prepend": {
      level: "ok",
      message: "~/.claude/CLAUDE.md updated — your content preserved below the managed block",
    },
  };
  const described = messages[result.action]
    ?? { level: "warn", message: `~/.claude/CLAUDE.md: unexpected sync result (${result.action})` };
  if (result.backupPath) {
    return { ...described, detail: `backup: ${result.backupPath}` };
  }
  return described;
}
