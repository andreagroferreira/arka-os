import {
  existsSync,
  cpSync,
  mkdirSync,
  rmSync,
  renameSync,
  copyFileSync,
} from "node:fs";
import { join, basename } from "node:path";

// Deploys a stable snapshot of the ArkaOS root (+ VERSION) into
// ~/.arkaos/lib. `.repo-path` points at whichever npx cache last ran an
// install/update — a location `npm cache clean` can purge at any time.
// When that happens, every `arka-py -m core.*` entrypoint (hooks,
// /arka update, telemetry CLIs) loses the package unless it runs from a
// dev checkout. The snapshot is the always-present fallback that
// bin/arka-py and core/hooks/_shared.py validate against.
//
// The snapshot must contain every directory the Python core reads
// root-relative, not just core/ itself — resolve_arkaos_root() hands the
// snapshot out as a full package root. Known readers: config/
// (content_syncer, policy_loader, settings_syncer), departments/
// (agent_provisioner), knowledge/ (registry_gen, registry/generator).
// A core/-only snapshot broke /arka update on a purged npx cache
// (v4.13.0: 75× missing user-claude.md, 704× missing agent files).
//
// core/sync/__init__.py is the validation marker: it distinguishes the
// full package from the cognitive scheduler's minimal core/ copy in
// ~/.arkaos/core (cognition + workflow only).
//
// Shared by installer/index.js (fresh install) and installer/update.js —
// same single-implementation rationale as hook-lib.js: the v4.3.2
// regression existed because two deploy loops drifted.
// core/ is deployed LAST: its sync/__init__.py is the validation marker
// resolve_arkaos_root() checks, so a crash mid-deploy on a fresh install
// leaves a snapshot that fails validation instead of a core-only root
// that validates but lacks config/departments/knowledge.
// scripts/ joined in Foundation PR-1: the auto-update daemon's launchd/
// systemd unit anchors at the snapshot (a unit pointing into the npx
// cache dies silently on `npm cache clean` — QG blocker). ~560K after
// the __pycache__ filter.
const SNAPSHOT_DIRS = ["config", "departments", "knowledge", "scripts", "core"];

export function deployCoreSnapshot(arkaosRoot, installDir) {
  if (!existsSync(join(arkaosRoot, "core", "sync", "__init__.py"))) return false;

  const libDir = join(installDir, "lib");
  for (const dir of SNAPSHOT_DIRS) {
    const src = join(arkaosRoot, dir);
    // Only core/ is guaranteed by the marker check above; a source
    // missing an optional dir keeps whatever snapshot already exists
    // rather than deleting it.
    if (!existsSync(src)) continue;
    swapInto(src, libDir, dir);
  }

  const versionFile = join(arkaosRoot, "VERSION");
  if (existsSync(versionFile)) copyFileSync(versionFile, join(libDir, "VERSION"));
  return true;
}

// Stage + swap so a crash at any point never destroys the last good
// snapshot: the new tree is fully written to staging first, the old
// snapshot is only moved aside (not deleted) before the swap, and its
// removal is the final step.
function swapInto(src, libDir, dir) {
  const dest = join(libDir, dir);
  const staging = join(libDir, `.${dir}.staging`);
  const previous = join(libDir, `.${dir}.previous`);

  rmSync(staging, { recursive: true, force: true });
  rmSync(previous, { recursive: true, force: true });
  mkdirSync(staging, { recursive: true });
  cpSync(src, staging, {
    recursive: true,
    filter: (path) => basename(path) !== "__pycache__",
  });
  if (existsSync(dest)) renameSync(dest, previous);
  renameSync(staging, dest);
  rmSync(previous, { recursive: true, force: true });
}
