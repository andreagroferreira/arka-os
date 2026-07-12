import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

// Persisted skills-deploy mode (F2-7c deprecation window, user-data
// pattern of v2.19): fresh installs default to the curated cut; update
// preserves whatever the machine already chose; machines predating the
// mode file stay on "full" WITH a deprecation notice — an update must
// never silently shrink an installed surface. Phase 2 (curated default
// for everyone + whitelist-only sweep) ships separately, gated on
// doctor telemetry about how many installs remain "full".

const MODE_FILE = () => join(homedir(), ".arkaos", "skills-mode.json");
const VALID_MODES = new Set(["curated", "full"]);

export function readSkillsMode() {
  try {
    const data = JSON.parse(readFileSync(MODE_FILE(), "utf-8"));
    return VALID_MODES.has(data.mode) ? data.mode : null;
  } catch {
    return null;
  }
}

export function writeSkillsMode(mode) {
  if (!VALID_MODES.has(mode)) return false;
  try {
    mkdirSync(join(homedir(), ".arkaos"), { recursive: true });
    writeFileSync(MODE_FILE(), JSON.stringify({ mode }) + "\n");
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the mode for THIS run. `flag` is the --skills CLI value
 * (persisted when valid); `fresh` marks a fresh install (no mode file
 * -> curated). Returns { mode, deprecated } where `deprecated` flags a
 * legacy full-mode machine that should see the migration notice.
 */
export function resolveSkillsMode({ flag = "", fresh = false } = {}) {
  if (VALID_MODES.has(flag)) {
    writeSkillsMode(flag);
    return { mode: flag, deprecated: false };
  }
  const persisted = readSkillsMode();
  if (persisted) return { mode: persisted, deprecated: false };
  if (fresh) {
    writeSkillsMode("curated");
    return { mode: "curated", deprecated: false };
  }
  return { mode: "full", deprecated: true };
}

export function deprecationNotice() {
  return (
    "[arka:deprecated] Full skill set (274) is deprecated; the default "
    + "becomes the curated 69 in a future release. Switch now: "
    + "npx arkaos update --skills curated (a la carte packs: "
    + "/plugin install arkaos-<dept>@arkaos). Opt out permanently: "
    + "npx arkaos update --skills full"
  );
}
