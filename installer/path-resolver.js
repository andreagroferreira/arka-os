/**
 * Path template resolver for the ArkaOS installer (Node.js side).
 *
 * Mirrors core/runtime/path_resolver.py just enough to substitute
 * ${VAULT_PATH}, ${ARKA_OS_REPOS}, ${PROJECT_ROOTS}, ${GIT_HOST}, ${HOME}
 * inside SKILL.md, cognition prompts and other markdown that the installer
 * copies to the user's ~/.claude/skills/arka/ tree or ~/.arkaos/.
 *
 * Source files contain templates so the arka-os repo stays portable across
 * the 20K user base. The installer rewrites tokens at copy-time so each
 * user's installation has concrete paths.
 *
 * The Python module is the single source of truth for the substitution
 * contract. Keep this file in sync. See core/specs/SPEC-paths-portability.md.
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const TOKEN_PATTERN = /\$\{([A-Z_]+)\}/g;
const DEFAULT_PROJECT_ROOTS = ["~/Herd", "~/Work", "~/AIProjects"];
const DEFAULT_REPOS_ROOT = "~/AIProjects";
const DEFAULT_GIT_HOST = "github.com";

let _profileCache = null;

function profilePath() {
  return join(homedir(), ".arkaos", "profile.json");
}

export function loadProfile({ refresh = false } = {}) {
  if (_profileCache && !refresh) return _profileCache;

  const path = profilePath();
  if (!existsSync(path)) {
    // Installer can be invoked before profile.json exists (first install).
    // Caller decides whether to treat that as fatal.
    return null;
  }
  let raw;
  try {
    raw = JSON.parse(readFileSync(path, "utf8"));
  } catch (err) {
    throw new Error(
      `~/.arkaos/profile.json could not be parsed (${err.message}). ` +
      `Run /arka setup to repair, or restore from a .bak file.`
    );
  }

  const vaultPath = raw.vaultPath || raw.vault_path || "";
  const reposRoot = raw.reposRoot || raw.repos_root || DEFAULT_REPOS_ROOT;
  const projectRoots = Array.isArray(raw.projectRoots) && raw.projectRoots.length
    ? raw.projectRoots
    : deriveProjectRoots(raw.projectsDir || "");

  _profileCache = {
    version: String(raw.version || "2"),
    vaultPath,
    reposRoot,
    projectRoots,
    raw,
  };
  return _profileCache;
}

export function resetCache() {
  _profileCache = null;
}

export function resolveString(template, options = {}) {
  if (typeof template !== "string" || !template.includes("${")) return template;
  const profile = options.profile || loadProfile();
  return template.replace(TOKEN_PATTERN, (match, name) =>
    resolveToken(name, match, profile)
  );
}

export function resolveFile(srcPath, dstPath, options = {}) {
  const content = readFileSync(srcPath, "utf8");
  const resolved = resolveString(content, options);
  writeFileSync(dstPath, resolved, "utf8");
}

function resolveToken(name, original, profile) {
  if (name === "HOME") return homedir();
  if (name === "GIT_HOST") {
    return envOr("ARKAOS_GIT_HOST", DEFAULT_GIT_HOST);
  }
  if (name === "VAULT_PATH") {
    const envValue = envOr("ARKAOS_VAULT_PATH", envOr("ARKAOS_VAULT", ""));
    if (envValue) return envValue;
    return profile?.vaultPath || original;
  }
  if (name === "ARKA_OS_REPOS") {
    const envValue = envOr("ARKAOS_REPOS_ROOT", "");
    if (envValue) return envValue;
    return profile?.reposRoot || original;
  }
  if (name === "PROJECT_ROOTS") {
    const envValue = envOr("ARKAOS_PROJECT_ROOTS", "");
    if (envValue) return envValue;
    const roots = profile?.projectRoots || DEFAULT_PROJECT_ROOTS;
    const sep = process.platform === "win32" ? ";" : ":";
    return roots.join(sep);
  }
  return original;
}

function envOr(name, fallback) {
  const value = process.env[name];
  return value && value.length > 0 ? value : fallback;
}

function deriveProjectRoots(projectsDirText) {
  if (!projectsDirText) return [...DEFAULT_PROJECT_ROOTS];
  const posix = /(?:\/Users|\/home)\/\S+?\/(?:Herd|Work|AIProjects|code|repos)/g;
  const windows = /[A-Z]:\\Users\\[^\s\\]+\\(?:Herd|Work|AIProjects|code|repos)/g;
  const found = [
    ...(projectsDirText.match(posix) || []),
    ...(projectsDirText.match(windows) || []),
  ];
  return found.length > 0 ? found : [...DEFAULT_PROJECT_ROOTS];
}
