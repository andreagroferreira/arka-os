// Graphify — code knowledge-graph grounding layer for `npx arkaos install`
// and `npx arkaos@latest update`.
//
// Graphify (PyPI package `graphifyy`, CLI `graphify`) extracts a local
// tree-sitter code graph into `<project>/graphify-out/graph.json` with
// EXTRACTED/INFERRED/AMBIGUOUS confidence tags. ArkaOS uses that graph as
// the official grounding layer (Synapse L2.7) so answers about a codebase
// cite real nodes + source locations instead of inventing structure.
//
// Install strategy (best-effort, in order):
//   1. `graphify` already on PATH             → no-op.
//   2. `uv tool install graphifyy`  (preferred)
//   3. `pipx install graphifyy`     (fallback)
//   4. Neither manager available   → print a one-line manual hint.
// Then `graphify install` registers the Graphify skill with AI assistants
// (same best-effort tolerance).
//
// Invariants (.claude/rules/node-installer.md):
//   - ESM, os.homedir()/path.join only, never hardcoded paths.
//   - No interactive prompts; safe in headless/CI runs.
//   - Never throws — the installer must NEVER fail because of Graphify.

import { execSync, spawnSync } from "node:child_process";
import {
  existsSync, readFileSync, writeFileSync, chmodSync, renameSync, unlinkSync,
} from "node:fs";
import { createInterface } from "node:readline";
import { isIP } from "node:net";
import { homedir } from "node:os";
import { join } from "node:path";
import { CMD_FINDER } from "./platform.js";

const PYPI_PACKAGE = "graphifyy"; // double y — the CLI binary is `graphify`
const MANUAL_HINT =
  "Graphify not installed — install manually: uv tool install graphifyy (or pipx install graphifyy)";

// --- Graphify HTTP knowledge-graph MCP (user-scope, config-driven) --------
// A SEPARATE concern from the stdio CLI above: a central, always-on
// knowledge-graph server (query_graph, god_nodes, shortest_path, …) that
// grounds answers like the Obsidian vault does. The endpoint is per-user
// (home LAN / localhost / VPS), so URL + token are configurable and never
// hardcoded: url in ~/.arkaos/config.json (knowledge.graphify.url), token
// in ~/.arkaos/keys.json (GRAPHIFY_TOKEN). Registered at Claude Code user
// scope so it is available in every project without per-project .mcp.json
// duplication. "Active once configured": applied only when enabled !== false
// AND both url and token resolve.
const GRAPHIFY_TOKEN_ENV = "GRAPHIFY_TOKEN";
const GRAPHIFY_URL_ENV = "GRAPHIFY_URL";

function findBinary(name) {
  try {
    const out = execSync(`${CMD_FINDER} ${name}`, {
      stdio: ["ignore", "pipe", "ignore"],
    }).toString().trim().split(/\r?\n/)[0];
    return out || null;
  } catch {
    return null;
  }
}

function readVersion(command) {
  try {
    const out = execSync(command, { stdio: ["ignore", "pipe", "ignore"] }).toString();
    const match = out.match(/(\d+\.\d+(?:\.\d+)?)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

// Try one package-manager install of `graphifyy`. Returns true when the
// child exited 0. Never throws.
function tryInstallVia(manager) {
  const args = manager === "uv" ? ["tool", "install", PYPI_PACKAGE] : ["install", PYPI_PACKAGE];
  const out = spawnSync(manager, args, {
    timeout: 180_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  return !out.error && out.status === 0;
}

// Run `graphify install` so the Graphify skill registers with the AI
// assistant runtimes it detects. Best-effort: failure is reported in the
// status object, never thrown.
function runGraphifySkillInstall() {
  const out = spawnSync("graphify", ["install"], {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  if (out.error || out.status !== 0) {
    const reason = (out.stderr || out.error?.message || "unknown").trim().slice(0, 200);
    return { action: "failed", reason };
  }
  return { action: "installed" };
}

/**
 * Ensure the Graphify CLI is present and its skill is registered.
 *
 * Returns a status object — never throws, never blocks the install:
 *   { binary: { installed, location?, version?, action, hint? },
 *     skillInstall: { action, reason? } }
 *
 * `options.dryRun` skips installation attempts and `graphify install`.
 */
export function ensureGraphify(options = {}) {
  const result = { binary: null, skillInstall: { action: "skipped", reason: "binary-missing" } };
  try {
    let location = findBinary("graphify");

    if (!location && !options.dryRun) {
      if (findBinary("uv") && tryInstallVia("uv")) {
        location = findBinary("graphify");
      } else if (findBinary("pipx") && tryInstallVia("pipx")) {
        location = findBinary("graphify");
      }
    }

    if (!location) {
      result.binary = {
        installed: false,
        action: options.dryRun ? "dry-run" : "manual-install-needed",
        hint: MANUAL_HINT,
      };
      return result;
    }

    result.binary = {
      installed: true,
      location,
      version: readVersion("graphify --version"),
      action: "present",
    };

    if (options.dryRun) {
      result.skillInstall = { action: "skipped", reason: "dry-run" };
    } else {
      result.skillInstall = runGraphifySkillInstall();
    }
    return result;
  } catch (err) {
    result.binary = result.binary || {
      installed: false,
      action: "check-failed",
      hint: MANUAL_HINT,
    };
    result.skillInstall = { action: "failed", reason: err.message };
    return result;
  }
}

function arkaosPath(home, ...parts) {
  return join(home, ".arkaos", ...parts);
}

function readJson(path) {
  if (!existsSync(path)) return {};
  try { return JSON.parse(readFileSync(path, "utf-8")); } catch { return {}; }
}

/**
 * Resolve the graphify HTTP config from disk + environment. Pure/no side
 * effects. Precedence: env overrides config (url) / keys.json (token).
 *   { enabled, url, token, ready }
 * `ready` is true only when enabled !== false AND url AND token all resolve.
 */
export function resolveGraphifyHttpConfig({ home = homedir(), env = process.env } = {}) {
  const config = readJson(arkaosPath(home, "config.json"));
  const keys = readJson(arkaosPath(home, "keys.json"));
  const gcfg = (config.knowledge && config.knowledge.graphify) || {};

  const enabled = gcfg.enabled !== false; // default ON ("active once configured")
  const url = validGraphifyUrl((env[GRAPHIFY_URL_ENV] || gcfg.url || "").trim());
  const token = (keys[GRAPHIFY_TOKEN_ENV] || env[GRAPHIFY_TOKEN_ENV] || "").trim();

  return { enabled, url, token, ready: enabled && Boolean(url) && Boolean(token) };
}

// The Bearer token is read from keys.json but the URL can come from the
// environment, so an unvalidated endpoint means anyone who controls
// GRAPHIFY_URL redirects the operator's credential. Accept only http(s), and
// only allow plaintext http for a loopback or private-range host — the home
// LAN / localhost case this feature exists for. Anything else resolves to ""
// (not configured), which is the fail-open path.
function validGraphifyUrl(raw) {
  if (!raw) return "";
  // Judge the RAW authority first: WHATWG `new URL()` silently normalises
  // obfuscated IPs (0177.0.0.1 -> 127.0.0.1) and reads `http:///mcp` as the
  // host "mcp", so a post-parse check cannot see either. The Python twin
  // rejects both, and an operator never types them.
  if (!rawAuthorityIsPlain(raw)) return "";
  let parsed;
  try { parsed = new URL(raw); } catch { return ""; }
  if (parsed.protocol === "https:") return raw;
  if (parsed.protocol !== "http:") return "";
  return isPrivateHost(parsed.hostname) ? raw : "";
}

// False for an empty authority or any host label that is a bare number,
// 0x-hex, or 0-prefixed (octal) — the classic filter-bypass encodings.
function rawAuthorityIsPlain(raw) {
  const m = /^[a-zA-Z][\w+.-]*:\/\/([^/?#]*)/.exec(raw);
  if (!m) return true;                       // not authority-based; URL() decides
  let authority = m[1];
  if (authority.includes("@")) authority = authority.slice(authority.indexOf("@") + 1);
  const host = authority.replace(/:\d*$/, "").replace(/\.$/, "");
  if (!host) return false;                   // `http:///mcp`
  if (host.startsWith("[")) return true;     // IPv6 literal — no octal ambiguity
  if (/^(0[xX][0-9a-fA-F]+|\d+)$/.test(host)) return false;
  return !host.split(".").some((label) => /^0\d/.test(label));
}

// True only for hosts that cannot be a public endpoint.
//
// The checks are anchored and IP-aware on purpose. A previous version tested
// the hostname STRING with prefix regexes (/^10\./ etc.), which accepted
// `10.evil.example` — a domain anyone can register — and shipped the
// operator's Bearer token to it. Node also returns IPv6 hostnames WITH
// brackets, so a naive "no dot means local" rule classified every IPv6
// literal, public ones included, as private.
function isPrivateHost(rawHost) {
  // Node yields "[::1]" for IPv6 literals; net.isIP needs it unbracketed.
  let host = rawHost.startsWith("[") && rawHost.endsWith("]")
    ? rawHost.slice(1, -1)
    : rawHost;
  host = host.replace(/\.$/, "");            // trailing-dot FQDN
  if (!host) return false;                   // `http:///mcp` has no host
  if (host.includes("%")) host = host.split("%")[0];  // IPv6 zone-id
  // A bare numeric or hex label is an IP in disguise (134744072 == 8.8.8.8);
  // it must never reach the single-label "local name" fallback below.
  if (/^(0[xX][0-9a-fA-F]+|\d+)$/.test(host)) return false;

  const kind = isIP(host);
  if (kind === 4) {
    const o = host.split(".").map(Number);
    if (o.length !== 4 || o.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) {
      return false;
    }
    return (
      o[0] === 127 ||                                   // loopback
      o[0] === 10 ||                                    // 10/8
      (o[0] === 192 && o[1] === 168) ||                 // 192.168/16
      (o[0] === 172 && o[1] >= 16 && o[1] <= 31) ||     // 172.16/12
      (o[0] === 169 && o[1] === 254)                    // link-local
    );
  }
  if (kind === 6) {
    const v6 = host.toLowerCase();
    // ::1 loopback, fc00::/7 unique-local, fe80::/10 link-local.
    return v6 === "::1" || /^f[cd]/.test(v6) || /^fe[89ab]/.test(v6);
  }

  // Not an IP literal — a name.
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host.endsWith(".local")) return true;
  // Single-label name (`lab`, `nas`): resolvable only via /etc/hosts, mDNS or
  // a DNS search domain. A public host always carries a dot.
  return !host.includes(".");
}

// Persist the endpoint URL to config.json (knowledge.graphify.url), keeping
// enabled and any other keys intact. Never throws.
//
// Written to a sibling temp file then renamed, because rename is atomic on
// POSIX: a crash mid-write would otherwise leave truncated JSON, and readJson
// swallows a parse error into `{}` — silently discarding the operator's whole
// config. Same pattern PR #357 applied to the governance state file.
function saveGraphifyUrl(home, url) {
  const path = arkaosPath(home, "config.json");
  const tmp = `${path}.tmp-${process.pid}`;
  try {
    const config = readJson(path);
    config.knowledge = config.knowledge || {};
    config.knowledge.graphify = config.knowledge.graphify || {};
    config.knowledge.graphify.url = url;
    if (config.knowledge.graphify.enabled === undefined) {
      config.knowledge.graphify.enabled = true;
    }
    writeFileSync(tmp, JSON.stringify(config, null, 2) + "\n");
    renameSync(tmp, path);
  } catch {
    try { if (existsSync(tmp)) unlinkSync(tmp); } catch { /* best effort */ }
  }
}

// keys.json holds EVERY provider key, so it gets the same temp+rename
// treatment as config.json — a crash mid-write would otherwise truncate it
// and readJson turns unparseable JSON into {}, silently destroying the lot.
// The temp file is created at 0600 and renamed over the target, so the
// secret is never on disk world-readable: writeFileSync's `mode` applies
// only when creating, which is exactly why writing in place left a window.
function saveGraphifyToken(home, token) {
  const path = arkaosPath(home, "keys.json");
  const tmp = `${path}.tmp-${process.pid}`;
  try {
    const keys = readJson(path);
    keys[GRAPHIFY_TOKEN_ENV] = token;
    // `wx` = fail if the path exists. The temp name is predictable
    // (`${path}.tmp-${pid}`), and without this a planted symlink there would
    // be followed and the token written wherever it points.
    writeFileSync(tmp, JSON.stringify(keys, null, 2), { mode: 0o600, flag: "wx" });
    try { chmodSync(tmp, 0o600); } catch { /* best effort */ }
    renameSync(tmp, path);
  } catch {
    try { if (existsSync(tmp)) unlinkSync(tmp); } catch { /* best effort */ }
  }
}

// Never let a captured stderr echo a live credential into a log line.
function scrubSecrets(text) {
  return String(text || "").replace(/Bearer\s+\S+/gi, "Bearer ***");
}

function isClaudeCliAvailable() {
  try {
    execSync("claude --version", { stdio: "pipe", timeout: 5000 });
    return true;
  } catch { return false; }
}

// Current user-scope registration state for graphify: { registered, url }.
// url is parsed from `claude mcp get graphify` so we can detect endpoint
// changes and re-register only when needed.
function graphifyHttpState() {
  const out = spawnSync("claude", ["mcp", "get", "graphify"], {
    timeout: 10_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
  });
  if (out.status !== 0 || !out.stdout) return { registered: false, url: "" };
  const text = out.stdout;
  if (!/graphify/.test(text)) return { registered: false, url: "" };
  const m = text.match(/URL:\s*(\S+)/i);
  return { registered: true, url: m ? m[1].trim() : "" };
}

/**
 * Register (or refresh) the graphify HTTP MCP at Claude Code user scope.
 * Idempotent: skips when already registered with the same URL; re-registers
 * (remove + add) when the URL changed. Never throws.
 *
 * NOTE (known limitation, mirrors registerMagicMcp): the token is passed as
 * a CLI argument because `claude mcp add` has no stdin/file alternative — it
 * is briefly visible to `ps` while the child runs. It is NEVER written to
 * the repo or any log (only stderr is captured into `reason`).
 */
export function registerGraphifyHttpMcp({ runtime = "claude-code", url = "", token = "" } = {}) {
  if (runtime !== "claude-code") return { action: "skipped", reason: "runtime-not-claude-code" };
  if (!isClaudeCliAvailable()) return { action: "skipped", reason: "claude-cli-not-found" };
  if (!url || !token) return { action: "skipped", reason: "not-configured" };

  const state = graphifyHttpState();
  if (state.registered && state.url === url) return { action: "already-present" };
  if (state.registered) {
    // Endpoint changed — remove the stale registration first (best-effort).
    spawnSync("claude", ["mcp", "remove", "graphify", "-s", "user"], {
      timeout: 15_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8",
    });
  }

  const out = spawnSync("claude", [
    "mcp", "add", "graphify", "--scope", "user", "--transport", "http", url,
    "--header", `Authorization: Bearer ${token}`,
  ], { timeout: 60_000, stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8" });
  if (out.error || out.status !== 0) {
    const reason = scrubSecrets(out.stderr || out.error?.message || "unknown")
      .trim().slice(0, 200);
    return { action: "failed", reason };
  }
  return { action: state.registered ? "re-registered" : "registered" };
}

// TTY-gated endpoint prompt. Resolves to "" in headless contexts so the
// installer never blocks on a closed stdin (node-installer rule). Offers a
// localhost default; any other input is taken as a custom URL.
function promptGraphifyEndpoint() {
  if (!process.stdin.isTTY) return Promise.resolve("");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const q =
    "  Graphify knowledge-graph endpoint\n" +
    "    [enter] skip · 'l' localhost:8080 · or paste a full URL (http://host:8080/mcp): ";
  return new Promise((resolve) => {
    rl.question(q, (answer) => {
      rl.close();
      const a = (answer || "").trim();
      if (!a) return resolve("");
      if (a.toLowerCase() === "l") return resolve("http://localhost:8080/mcp");
      resolve(a);
    });
  });
}

function promptGraphifyToken() {
  if (!process.stdin.isTTY) return Promise.resolve("");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const q = "  Graphify Bearer token (leave empty to skip): ";
  return new Promise((resolve) => {
    rl.question(q, (answer) => { rl.close(); resolve((answer || "").trim()); });
  });
}

/**
 * Configure + register the graphify HTTP MCP. Single entry point wired into
 * installer/index.js and installer/update.js. Never throws.
 *
 * Interactive (TTY): when enabled and url/token are missing, prompts for the
 * endpoint + token and persists them. Headless/CI: acts only on already-saved
 * config (no prompt). Registers at user scope when the config is `ready`.
 */
/**
 * Last check before a LIVE token is handed to `claude mcp add`.
 *
 * `validGraphifyUrl` judges the string, which is right for the sync path but
 * lets a NAME through unresolved — and registration installs a persistent
 * credential that Claude Code then sends every session (QG M1). So resolve
 * here, where we are already async: a name that resolves PUBLICLY is refused;
 * one that does not resolve at all is accepted on form, so `npx arkaos
 * update` still works on a laptop away from the LAN.
 *
 * https endpoints are trusted on TLS, as everywhere else. Never throws.
 */
async function hostnameIsSafeToRegister(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:") return true;
    const host = parsed.hostname.replace(/^\[|\]$/g, "");
    if (isIP(host)) return isPrivateHost(parsed.hostname);
    const { lookup } = await import("node:dns/promises");
    let answers;
    try {
      answers = await lookup(host, { all: true });
    } catch {
      return true;  // unresolvable → off-LAN install, accept on form
    }
    return answers.length > 0 && answers.every((a) => isPrivateHost(a.address));
  } catch {
    return false;
  }
}

export async function configureGraphifyHttp({ runtime = "claude-code", home = homedir() } = {}) {
  try {
    let cfg = resolveGraphifyHttpConfig({ home });
    if (!cfg.enabled) return { action: "skipped", reason: "disabled" };

    // Interactive first-time setup: fill missing url/token from prompts.
    if ((!cfg.url || !cfg.token) && process.stdin.isTTY) {
      if (!cfg.url) {
        const url = await promptGraphifyEndpoint();
        if (url) saveGraphifyUrl(home, url);
      }
      if (!cfg.token) {
        const token = await promptGraphifyToken();
        if (token) {
          saveGraphifyToken(home, token);
          console.log("         Graphify token saved to ~/.arkaos/keys.json (chmod 600).");
        }
      }
      cfg = resolveGraphifyHttpConfig({ home });
    }

    if (!cfg.ready) return { action: "skipped", reason: cfg.url ? "no-token" : "not-configured" };
    if (!(await hostnameIsSafeToRegister(cfg.url))) {
      return { action: "skipped", reason: "endpoint-resolves-publicly" };
    }
    return registerGraphifyHttpMcp({ runtime, url: cfg.url, token: cfg.token });
  } catch (err) {
    // Scrubbed for symmetry: no current path routes the token here, but this
    // reason is logged by index.js/update.js like every other sink.
    return { action: "failed", reason: scrubSecrets(err?.message || "unknown").slice(0, 200) };
  }
}

/**
 * Doctor check for installer/doctor.js — is the `graphify` binary present,
 * and at which version? Never throws.
 */
export function graphifyDoctor() {
  try {
    const location = findBinary("graphify");
    if (!location) {
      return { installed: false, location: null, version: null, hint: MANUAL_HINT };
    }
    return {
      installed: true,
      location,
      version: readVersion("graphify --version"),
      hint: null,
    };
  } catch {
    return { installed: false, location: null, version: null, hint: MANUAL_HINT };
  }
}
