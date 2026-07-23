/**
 * Profile → service reconciliation (Foundation PR-4).
 *
 * Reads config/install-profiles.json (data-driven manifest: profiles
 * extend each other, services carry a kind + probe metadata) and brings
 * a machine up to its persisted install profile:
 *
 *   probe installed? → present (zero side-effects, idempotent)
 *   missing          → install via the EXISTING helpers (pipInstall,
 *                      package-manager, system-tools, graphify) — or a
 *                      hint when the install needs consent we don't have
 *
 * Consent rules (.claude/rules/node-installer.md + campaign spec):
 *   - NEVER sudo, NEVER brew/winget without consent.
 *   - Headless runs (update daemon, CI) only touch consent-free
 *     services (pip into our own venv, ollama pull of the configured
 *     model); everything else reports a copy-paste hint.
 *   - NEVER uninstalls or downgrades anything.
 *
 * Effects are injected: `defaultEffects()` carries the real
 * implementations; tests inject stubs so no real install ever runs in
 * the suite (feedback_destructive_tests).
 */

import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { getArkaosPython, pipInstall } from "./python-resolver.js";
import { checkOllama, ensureSystemTools } from "./system-tools.js";
import {
  buildInstallCommand,
  detectPackageManager,
  installViaPackageManager,
  managerNeedsSudo,
} from "./package-manager.js";
import { ensureGraphify, graphifyDoctor } from "./graphify.js";
import { CMD_FINDER } from "./platform.js";
import { DEFAULT_PROFILE, normalizeProfileFlag } from "./profile.js";

// ── Manifest ──────────────────────────────────────────────────────────────

/**
 * Load and validate config/install-profiles.json. Throws a descriptive
 * Error on structural problems (missing sections, dangling service
 * refs, dangling/cyclic extends) so a broken manifest fails loudly in
 * tests and surfaces as a doctor warn at runtime — callers wrap in
 * try/catch.
 */
export function loadProfilesManifest(repoRoot) {
  const path = join(repoRoot, "config", "install-profiles.json");
  const manifest = JSON.parse(readFileSync(path, "utf-8"));
  validateManifest(manifest);
  return manifest;
}

function validateManifest(manifest) {
  if (!manifest || typeof manifest !== "object") {
    throw new Error("install-profiles manifest is not an object");
  }
  const { profiles, services } = manifest;
  if (!profiles || typeof profiles !== "object" || Object.keys(profiles).length === 0) {
    throw new Error("install-profiles manifest has no profiles");
  }
  if (!services || typeof services !== "object") {
    throw new Error("install-profiles manifest has no services");
  }
  for (const [name, profile] of Object.entries(profiles)) {
    if (!Array.isArray(profile.services)) {
      throw new Error(`profile "${name}" has no services array`);
    }
    for (const id of profile.services) {
      if (!services[id]) {
        throw new Error(`profile "${name}" references unknown service "${id}"`);
      }
    }
    if (profile.extends !== undefined && !profiles[profile.extends]) {
      throw new Error(`profile "${name}" extends unknown profile "${profile.extends}"`);
    }
  }
  // Acyclic extends: walk every chain; a revisit is a cycle.
  for (const name of Object.keys(profiles)) {
    const seen = new Set();
    let cursor = name;
    while (cursor !== undefined) {
      if (seen.has(cursor)) {
        throw new Error(`cyclic extends chain at profile "${cursor}"`);
      }
      seen.add(cursor);
      cursor = profiles[cursor].extends;
    }
  }
  for (const [id, svc] of Object.entries(services)) {
    if (!svc || typeof svc !== "object" || typeof svc.kind !== "string") {
      throw new Error(`service "${id}" has no kind`);
    }
    for (const dep of svc.requires || []) {
      if (!services[dep]) {
        throw new Error(`service "${id}" requires unknown service "${dep}"`);
      }
    }
  }
}

/**
 * Resolve the ordered, deduplicated service list for a profile:
 * extends-parents first (essential before complete before local-ai),
 * preserving each profile's declared order. Pure.
 */
export function resolveServicesForProfile(name, manifest) {
  const profiles = manifest.profiles;
  const canonical = normalizeProfileFlag(name) || name;
  if (!profiles[canonical]) {
    throw new Error(`unknown install profile: ${name}`);
  }
  const chain = [];
  const seen = new Set();
  let cursor = canonical;
  while (cursor !== undefined) {
    if (seen.has(cursor)) {
      throw new Error(`cyclic extends chain at profile "${cursor}"`);
    }
    seen.add(cursor);
    chain.unshift(cursor); // parent-first
    cursor = profiles[cursor].extends;
    if (cursor !== undefined && !profiles[cursor]) {
      throw new Error(`profile extends unknown profile "${cursor}"`);
    }
  }
  const out = [];
  const dedup = new Set();
  for (const profileName of chain) {
    for (const id of profiles[profileName].services || []) {
      if (!dedup.has(id)) {
        dedup.add(id);
        out.push(id);
      }
    }
  }
  return out;
}

// ── Model Fabric: execution model parser ─────────────────────────────────

// Minimal, tolerant YAML-subset parser (nested maps of scalars, 2-space
// indent) — enough for ~/.arkaos/models.yaml, ZERO new dependencies.
// Unparseable lines and lists are skipped, never thrown on.
function parseSimpleYaml(text) {
  const root = {};
  const stack = [{ indent: -1, node: root }];
  for (const rawLine of String(text).split(/\r?\n/)) {
    const line = rawLine.replace(/\t/g, "  ");
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("- ")) continue;
    const m = trimmed.match(/^([A-Za-z0-9_./-]+):\s*(.*)$/);
    if (!m) continue;
    const indent = line.length - line.trimStart().length;
    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) {
      stack.pop();
    }
    const parent = stack[stack.length - 1].node;
    const key = m[1];
    // A value that is only a comment (`key: # note`) is an empty scalar
    // in YAML — treat it like `key:` (nested map or empty).
    const rawValue = m[2].startsWith("#") ? "" : m[2];
    if (rawValue === "") {
      const child = {};
      parent[key] = child;
      stack.push({ indent, node: child });
    } else {
      parent[key] = unquoteScalar(rawValue);
    }
  }
  return root;
}

// YAML scalar semantics for the subset we accept: a quoted value keeps
// everything between the quotes (a "#" inside quotes is data); an
// unquoted value ends at the first whitespace-preceded "#" (inline
// comment), matching the canonical Python reader.
function unquoteScalar(raw) {
  const quote = raw[0];
  if (quote === '"' || quote === "'") {
    const end = raw.indexOf(quote, 1);
    if (end !== -1) return raw.slice(1, end);
  }
  const hash = raw.search(/\s#/);
  return (hash === -1 ? raw : raw.slice(0, hash)).trim();
}

/**
 * Read the Model Fabric execution model from ~/.arkaos/models.yaml.
 * Returns { model, effort } only when roles.execution routes to the
 * ollama provider with a non-empty model (alias slots best/default/fast
 * resolve through aliases.ollama). Missing file, corrupt YAML, or a
 * non-ollama execution role → null (callers skip with a hint).
 */
export function parseExecutionModel(
  modelsYamlPath = join(homedir(), ".arkaos", "models.yaml"),
) {
  try {
    if (!existsSync(modelsYamlPath)) return null;
    const doc = parseSimpleYaml(readFileSync(modelsYamlPath, "utf-8"));
    const role = doc && doc.roles && doc.roles.execution;
    if (!role || typeof role !== "object") return null;
    const provider = typeof role.provider === "string" ? role.provider.trim() : "";
    if (provider !== "ollama" && !provider.startsWith("ollama/")) return null;
    let model = typeof role.model === "string" ? role.model.trim() : "";
    // Embedded form "provider: ollama/<model>" (CLAUDE.md shorthand).
    if (!model && provider.startsWith("ollama/")) {
      model = provider.slice("ollama/".length);
    }
    // Alias slot (best/default/fast) → aliases.ollama lookup.
    const aliases = doc.aliases && doc.aliases.ollama;
    if (model && aliases && typeof aliases === "object" && typeof aliases[model] === "string") {
      model = aliases[model].trim();
    }
    if (!model) return null;
    return { model, effort: typeof role.effort === "string" ? role.effort : "" };
  } catch {
    return null;
  }
}

// ── Effects (real defaults; tests inject stubs) ───────────────────────────

// Model names come from the user's own config, but they end up on a
// command line — refuse anything outside the ollama name grammar.
const SAFE_MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]*$/;

export function defaultEffects() {
  return {
    pyImport(module) {
      const py = getArkaosPython();
      if (!py) return false;
      try {
        execSync(`"${py}" -c "import ${module}"`, { stdio: "ignore", timeout: 30000 });
        return true;
      } catch {
        return false;
      }
    },
    pipInstall(packages) {
      return pipInstall(packages, { timeout: 300000, log: () => {} });
    },
    commandExists(bin) {
      try {
        execSync(`${CMD_FINDER} ${bin}`, { stdio: ["ignore", "ignore", "ignore"] });
        return true;
      } catch {
        return false;
      }
    },
    fileExists(path) {
      return existsSync(path);
    },
    checkOllama() {
      return checkOllama();
    },
    ensureOllama() {
      const sys = ensureSystemTools({ withOllama: true });
      return sys.ollama || null;
    },
    detectManager() {
      return detectPackageManager();
    },
    installSystemPackage(pkg, manager) {
      return installViaPackageManager(pkg, { manager });
    },
    ollamaList() {
      try {
        return execSync("ollama list", {
          stdio: ["ignore", "pipe", "ignore"],
          timeout: 10000,
        }).toString();
      } catch {
        return null;
      }
    },
    ollamaPull(model) {
      try {
        execSync(`ollama pull ${model}`, { stdio: "pipe", timeout: 1800000 });
        return true;
      } catch {
        return false;
      }
    },
    resolveExecutionModel() {
      return parseExecutionModel();
    },
    graphifyInstalled() {
      try {
        return !!graphifyDoctor().installed;
      } catch {
        return false;
      }
    },
    ensureGraphify() {
      try {
        return ensureGraphify();
      } catch {
        return null;
      }
    },
    // Headless-safe default: no TTY conversation here — interactive
    // callers (install wizard, future PRs) inject a real confirm.
    async confirm() {
      return false;
    },
  };
}

// ── Reconciliation ────────────────────────────────────────────────────────

/**
 * Bring the machine up to `profile`. Returns an ordered array of
 * { id, label, status, hint? } with status ∈ present|installed|skipped|
 * failed. Never throws for a single service (failure → status "failed"
 * + continue); throws only when the manifest itself is unloadable.
 */
export async function reconcileServices({
  profile,
  repoRoot,
  interactive = false,
  effects = null,
  log = () => {},
} = {}) {
  const fx = { ...defaultEffects(), ...(effects || {}) };
  const manifest = loadProfilesManifest(repoRoot);
  const canonical = normalizeProfileFlag(profile) || DEFAULT_PROFILE;
  const ids = resolveServicesForProfile(canonical, manifest);
  const results = [];
  const statusById = new Map();
  for (const id of ids) {
    const svc = manifest.services[id];
    let result;
    try {
      result = await reconcileOne(id, svc, { fx, interactive, statusById });
    } catch (err) {
      // A single service must never abort the reconciliation run.
      log(`         ⚠ ${svc.label || id}: ${err.message}`);
      result = { id, label: svc.label || id, status: "failed", hint: err.message };
    }
    statusById.set(id, result.status);
    results.push(result);
  }
  return results;
}

async function reconcileOne(id, svc, { fx, interactive, statusById }) {
  const base = { id, label: svc.label || id };

  // Dependency gate: a service whose prerequisite is not on the machine
  // (skipped/failed this run) is skipped, never attempted blind.
  for (const dep of svc.requires || []) {
    const depStatus = statusById.get(dep);
    if (depStatus && depStatus !== "present" && depStatus !== "installed") {
      return { ...base, status: "skipped", hint: `requires ${dep} (${depStatus})` };
    }
  }

  switch (svc.kind) {
    case "pip": {
      const modules = Array.isArray(svc.modules) ? svc.modules : [];
      const present = modules.length > 0 && modules.every((m) => fx.pyImport(m));
      if (present) return { ...base, status: "present" };
      return fx.pipInstall(svc.packages)
        ? { ...base, status: "installed" }
        : {
            ...base,
            status: "failed",
            hint: `run: ~/.arkaos/venv/bin/pip install '${svc.packages}'`,
          };
    }

    case "system-package": {
      if (fx.commandExists(svc.binary)) return { ...base, status: "present" };
      const manager = fx.detectManager();
      const pkg = manager && svc.packages ? svc.packages[manager] : null;
      const command = manager && pkg ? buildInstallCommand(manager, pkg) : null;
      const hint = command ? `run: ${command}` : `install ${svc.binary} manually`;
      // Consent gate: system packages touch the OS — never headless,
      // never sudo, only on an explicit yes.
      if (!interactive) return { ...base, status: "skipped", hint };
      if (!manager || !pkg) return { ...base, status: "skipped", hint };
      if (managerNeedsSudo(manager)) {
        return { ...base, status: "skipped", hint: `needs sudo — ${hint}` };
      }
      const agreed = await fx.confirm(`Install ${base.label} now? (${command})`);
      if (!agreed) return { ...base, status: "skipped", hint };
      const r = fx.installSystemPackage(pkg, manager);
      return r && r.installed
        ? { ...base, status: "installed" }
        : { ...base, status: "failed", hint };
    }

    case "ollama": {
      const st = fx.checkOllama();
      if (st && st.installed) {
        // Installed but not running is still "present" — reconciliation
        // installs software, it does not manage daemons.
        return st.needsAction === "none"
          ? { ...base, status: "present" }
          : { ...base, status: "present", hint: st.suggestedCommand || "not running — start Ollama" };
      }
      const hint = (st && st.suggestedCommand)
        ? `run: ${st.suggestedCommand}`
        : "install from https://ollama.com/download";
      if (!interactive) return { ...base, status: "skipped", hint };
      if (st && st.needsSudo) return { ...base, status: "skipped", hint: `needs sudo — ${hint}` };
      const agreed = await fx.confirm("Install Ollama (local LLM runtime) now?");
      if (!agreed) return { ...base, status: "skipped", hint };
      const tool = fx.ensureOllama();
      return tool && tool.installed
        ? { ...base, status: "installed" }
        : { ...base, status: "failed", hint };
    }

    case "ollama-model": {
      const resolved = fx.resolveExecutionModel();
      if (!resolved || !resolved.model) {
        return {
          ...base,
          status: "skipped",
          hint: "no ollama execution role in ~/.arkaos/models.yaml (npx arkaos models set execution ollama/<model>)",
        };
      }
      const model = resolved.model;
      const list = fx.ollamaList();
      if (list === null) {
        return { ...base, status: "skipped", hint: "ollama not reachable — start it and re-run" };
      }
      if (ollamaListHasModel(list, model)) return { ...base, status: "present" };
      if (!SAFE_MODEL_RE.test(model)) {
        return { ...base, status: "failed", hint: `refusing to pull unsafe model name "${model}"` };
      }
      return fx.ollamaPull(model)
        ? { ...base, status: "installed" }
        : { ...base, status: "failed", hint: `run: ollama pull ${model}` };
    }

    case "file": {
      const path = expandHome(svc.path);
      return fx.fileExists(path)
        ? { ...base, status: "present" }
        : { ...base, status: "failed", hint: svc.hint || `missing ${path}` };
    }

    case "graphify": {
      if (fx.graphifyInstalled()) return { ...base, status: "present" };
      // ensureGraphify is the existing best-effort installer (uv/pipx,
      // non-sudo) already run unconditionally by install/update — same
      // consent posture here.
      const g = fx.ensureGraphify();
      const installed = !!(g && g.binary && g.binary.installed);
      if (installed) return { ...base, status: "installed" };
      return {
        ...base,
        status: "skipped",
        hint: (g && g.binary && g.binary.hint) || "run: uv tool install graphifyy",
      };
    }

    default:
      return { ...base, status: "skipped", hint: `unknown service kind "${svc.kind}"` };
  }
}

function expandHome(path) {
  const p = String(path || "");
  if (p === "~") return homedir();
  if (p.startsWith("~/")) return join(homedir(), p.slice(2));
  return p;
}

/** Match a model against `ollama list` output (NAME first column). */
export function ollamaListHasModel(output, model) {
  for (const line of String(output).split(/\r?\n/)) {
    const token = line.trim().split(/\s+/)[0];
    if (!token || token.toLowerCase() === "name") continue;
    if (token === model) return true;
    if (!model.includes(":")) {
      if (token === `${model}:latest` || token.split(":")[0] === model) return true;
    }
  }
  return false;
}
