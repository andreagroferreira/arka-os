/**
 * Install profiles — pure, testable helpers (Foundation PR-3).
 *
 * A profile names WHAT gets provisioned on a machine:
 *
 *   essential  venv, hooks, skills, dashboard, MCPs
 *   complete   essential + litellm[proxy] + ffmpeg
 *   local-ai   complete + Ollama + local execution model
 *
 * In PR-3 the chosen profile is only PERSISTED (profile.json,
 * `installProfile` key) — provisioning of the extra tiers lands in
 * PR-4. Keeping the record builder here (instead of inline in
 * installer/index.js) makes the persistence contract unit-testable
 * without touching the filesystem.
 */

export const INSTALL_PROFILES = ["essential", "complete", "local-ai"];

export const DEFAULT_PROFILE = "essential";

/** Human-readable hint per profile — single source for both wizards. */
export const PROFILE_HINTS = {
  essential: "venv, hooks, skills, dashboard, MCPs",
  complete: "essential + litellm[proxy] + ffmpeg",
  "local-ai": "complete + Ollama + local execution model",
};

/**
 * Normalize a user-supplied profile value (CLI flag, profile.json field).
 * Returns the canonical profile string, or null when invalid/empty so
 * callers can distinguish "not provided" from "provided and valid".
 */
export function normalizeProfileFlag(value) {
  if (typeof value !== "string") return null;
  const v = value.trim().toLowerCase();
  return INSTALL_PROFILES.includes(v) ? v : null;
}

/**
 * Build the profile.json record persisted by installer/index.js.
 *
 * Mirrors the object previously built inline in install() step 11, plus
 * the `installProfile` key. `created` is preserved from the previous
 * record when present (upgrade), `updated` is always now.
 */
export function buildProfileRecord(userConfig = {}, previousProfile = null) {
  const prev =
    previousProfile && typeof previousProfile === "object" ? previousProfile : {};
  return {
    version: "2",
    language: userConfig.language,
    market: userConfig.market,
    role: userConfig.role,
    company: userConfig.company,
    projectsDir: userConfig.projectsDir,
    vaultPath: userConfig.vaultPath,
    installProfile:
      normalizeProfileFlag(userConfig.installProfile) ||
      normalizeProfileFlag(prev.installProfile) ||
      DEFAULT_PROFILE,
    created: prev.created || new Date().toISOString(),
    updated: new Date().toISOString(),
  };
}
