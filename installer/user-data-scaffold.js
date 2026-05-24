// ~/.arkaos user-data scaffolding (PR28 v2.47.0).
//
// Run on every `npx arkaos install` and `npx arkaos@latest update`.
// Ensures the operator-mutable files and directories that the
// discipline-arc commands depend on exist:
//
//   - ~/.arkaos/redaction-clients.json  (leak scanner config)
//   - ~/.arkaos/reorganize-proposals/   (daily reorganizer output)
//
// Idempotent: never overwrites operator-authored content. On fresh
// installs, the redaction config is created with an empty `clients`
// list plus a `_doc` field explaining how to populate it.
//
// Returns a status object with one entry per scaffolded resource so
// the installer caller can log a human-readable line per run.

import {
  existsSync, mkdirSync, writeFileSync, renameSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";

const REDACTION_TEMPLATE = {
  _doc: (
    "Add real client/project identifiers (lowercase) to enable the leak "
    + "scanner. Empty `clients` list = scanner is a no-op (no false "
    + "positives in CI). See core/governance/leak_scanner.py."
  ),
  clients: [],
};

export function scaffoldArkaosUserData({ home = homedir() } = {}) {
  return {
    redaction: scaffoldRedactionConfig(home),
    proposals: scaffoldProposalsDir(home),
  };
}

function scaffoldRedactionConfig(home) {
  const path = join(home, ".arkaos", "redaction-clients.json");
  if (existsSync(path)) {
    return { action: "preserved", path };
  }
  mkdirSync(dirname(path), { recursive: true });
  // Atomic write: tmp + rename, matches config-seed.js convention.
  const tmp = `${path}.tmp-${process.pid}`;
  writeFileSync(tmp, JSON.stringify(REDACTION_TEMPLATE, null, 2) + "\n");
  renameSync(tmp, path);
  return { action: "created", path };
}

function scaffoldProposalsDir(home) {
  const path = join(home, ".arkaos", "reorganize-proposals");
  if (existsSync(path)) {
    return { action: "preserved", path };
  }
  mkdirSync(path, { recursive: true });
  return { action: "created", path };
}
