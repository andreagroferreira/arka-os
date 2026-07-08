import {
  existsSync,
  cpSync,
  mkdirSync,
  rmSync,
  renameSync,
  copyFileSync,
} from "node:fs";
import { join, basename } from "node:path";

// Deploys a stable snapshot of the Python core package (+ VERSION) into
// ~/.arkaos/lib. `.repo-path` points at whichever npx cache last ran an
// install/update — a location `npm cache clean` can purge at any time.
// When that happens, every `arka-py -m core.*` entrypoint (hooks,
// /arka update, telemetry CLIs) loses the core package unless it runs
// from a dev checkout. The snapshot is the always-present fallback that
// bin/arka-py and core/hooks/_shared.py validate against.
//
// core/sync/__init__.py is the validation marker: it distinguishes the
// full package from the cognitive scheduler's minimal core/ copy in
// ~/.arkaos/core (cognition + workflow only).
//
// Shared by installer/index.js (fresh install) and installer/update.js —
// same single-implementation rationale as hook-lib.js: the v4.3.2
// regression existed because two deploy loops drifted.
export function deployCoreSnapshot(arkaosRoot, installDir) {
  const srcCore = join(arkaosRoot, "core");
  if (!existsSync(join(srcCore, "sync", "__init__.py"))) return false;

  const libDir = join(installDir, "lib");
  const destCore = join(libDir, "core");
  const staging = join(libDir, ".core.staging");
  const previous = join(libDir, ".core.previous");

  // Stage + swap so a crash at any point never destroys the last good
  // snapshot: the new tree is fully written to staging first, the old
  // snapshot is only moved aside (not deleted) before the swap, and its
  // removal is the final step.
  rmSync(staging, { recursive: true, force: true });
  rmSync(previous, { recursive: true, force: true });
  mkdirSync(staging, { recursive: true });
  cpSync(srcCore, staging, {
    recursive: true,
    filter: (src) => basename(src) !== "__pycache__",
  });
  if (existsSync(destCore)) renameSync(destCore, previous);
  renameSync(staging, destCore);
  rmSync(previous, { recursive: true, force: true });

  const versionFile = join(arkaosRoot, "VERSION");
  if (existsSync(versionFile)) copyFileSync(versionFile, join(libDir, "VERSION"));
  return true;
}
