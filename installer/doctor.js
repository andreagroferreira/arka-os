import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { getArkaosPython, getVenvPython, canImportCore, getRepoRoot, diagnoseVenv, ensureVenvHealthy } from "./python-resolver.js";
import { IS_WINDOWS, HOOK_EXT, CMD_FINDER } from "./platform.js";
import { checkNode, checkObsidian, checkOllama } from "./system-tools.js";
import { graphifyDoctor } from "./graphify.js";
import { status as autoupdateStatus } from "./autoupdate.js";
import { normalizeProfileFlag, profileIncludes } from "./profile.js";
import {
  loadProfilesManifest,
  parseExecutionModel,
  resolveServicesForProfile,
} from "./services.js";

const INSTALL_DIR = join(homedir(), ".arkaos");

// ─── Install-profile awareness (Foundation PR-4) ────────────────────────
// Checks may declare `minProfile`; when the machine's persisted profile
// sits below it on the ladder (essential ⊂ complete ⊂ local-ai) the
// check reports "skipped (not in <profile> profile)" instead of a
// misleading warn — an essential machine without Ollama is healthy.

export function currentInstallProfile(
  profilePath = join(INSTALL_DIR, "profile.json")
) {
  try {
    const profile = JSON.parse(readFileSync(profilePath, "utf-8"));
    return normalizeProfileFlag(profile.installProfile) || "essential";
  } catch {
    return "essential";
  }
}

/** Null when the check applies; otherwise the human-readable skip reason. */
export function checkSkipReason(check, activeProfile) {
  if (!check.minProfile) return null;
  if (profileIncludes(activeProfile, check.minProfile)) return null;
  return `not in ${activeProfile} profile`;
}

// Resolve a single command via the platform-native locator. Returns true
// when the command is discoverable on PATH, false otherwise. stderr is
// suppressed through Node's stdio option so the probe does not print
// noise when the command is missing.
function commandExists(cmd) {
  const finder = CMD_FINDER;
  try {
    execSync(`${finder} ${cmd}`, { stdio: ["pipe", "pipe", "ignore"] });
    return true;
  } catch {
    return false;
  }
}

// Sentinel for the Hyperframes skill bundle. `npx skills add
// heygen-com/hyperframes` lands skills under ~/.claude/skills/<name>;
// the router skill is the sentinel. skillsDir is injectable for tests.
export function hyperframesSkillsInstalled(
  skillsDir = join(homedir(), ".claude", "skills")
) {
  return ["hyperframes", "hyperframes-core"].some((name) =>
    existsSync(join(skillsDir, name, "SKILL.md"))
  );
}

// SQLite self-heal (F1-D1) leaves the corrupt original as
// <db>.corrupt-<ts>.bak next to the recovered file. Their presence means
// a store healed itself — surface it so the operator can inspect/delete.
// baseDir is injectable for tests.
export function corruptDbBackups(baseDir = INSTALL_DIR) {
  try {
    return readdirSync(baseDir, { recursive: true })
      .map(String)
      .filter((name) => /\.corrupt-\d+\.bak$/.test(name));
  } catch {
    return [];
  }
}

// ─── Claude-layer probes (issue #358 migration) ─────────────────────────
// Migrated from the retired bash doctor's Claude-skills layer. Paths are
// injectable for tests. Three bash checks were deliberately NOT migrated
// because they audit v1-only artifacts with no v2 counterpart:
//   personas      — v2 deploys agents per-project via the sync engine
//   agent-memory  — superseded by the claude-mem plugin
//   capabilities  — v1 KB artifact (~/.arka-os/capabilities.json)

// The hook FILES living in ~/.arkaos/config/hooks (the hooks-dir check)
// prove nothing about whether Claude Code RUNS them. Governance is only
// live when ~/.claude/settings.json references the chain — a machine can
// have every script present, nothing wired, and a green doctor.
export function hooksWired(
  settingsPath = join(homedir(), ".claude", "settings.json")
) {
  if (!existsSync(settingsPath)) return true; // no Claude Code — not applicable
  try {
    const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
    return !!(settings.hooks && settings.hooks.UserPromptSubmit);
  } catch {
    return false; // unreadable settings = unverifiable wiring, surface it
  }
}

// Status line: configured AND the command it points at exists on disk.
export function statuslineConfigured(
  settingsPath = join(homedir(), ".claude", "settings.json")
) {
  if (!existsSync(settingsPath)) return true; // no Claude Code — not applicable
  try {
    const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
    const cmd = settings.statusLine && settings.statusLine.command;
    if (!cmd) return false;
    return existsSync(cmd);
  } catch {
    return false;
  }
}

// gotchas.json is live v2 state: the PostToolUse hook writes it
// (core/hooks/post_tool_use.py::_store_gotcha) and `/arka evolve`
// (#348) ingests it. Missing means capture never ran; corrupt means
// evolve will choke.
export function gotchasHealthy(
  gotchasPath = join(INSTALL_DIR, "gotchas.json")
) {
  if (!existsSync(gotchasPath)) return false;
  try {
    return Array.isArray(JSON.parse(readFileSync(gotchasPath, "utf-8")));
  } catch {
    return false;
  }
}

// The MCP registry ships inside the read-only arka skill bundle.
export function mcpRegistryHealthy(
  registryPath = join(
    homedir(), ".claude", "skills", "arka", "mcps", "registry.json")
) {
  if (!existsSync(registryPath)) return false;
  try {
    const reg = JSON.parse(readFileSync(registryPath, "utf-8"));
    return !!reg.mcpServers;
  } catch {
    return false;
  }
}

// Floor for "an ArkaOS skill set is deployed at all" — curated mode
// ships 37 core skills, so 7 is a deliberately low absence detector,
// not a completeness gauge (skills-surface judges completeness).
export function deployedSkillCount(
  skillsDir = join(homedir(), ".claude", "skills")
) {
  try {
    return readdirSync(skillsDir).filter(
      (dir) =>
        dir.startsWith("arka-") &&
        existsSync(join(skillsDir, dir, "SKILL.md"))
    ).length;
  } catch {
    return 0;
  }
}

// Recommended companion plugins (Superpowers + Claude-Mem). Probing
// spawns the claude CLI, so keep a hard timeout — a hung CLI must not
// stall the doctor (same rule as arka-tools-runner).
export function companionPluginsInstalled() {
  if (!commandExists("claude")) return true; // no Claude Code — not applicable
  try {
    const out = execSync("claude plugin list", {
      stdio: ["pipe", "pipe", "ignore"],
      timeout: 15000,
    }).toString();
    return out.includes("superpowers") && out.includes("claude-mem");
  } catch {
    return false;
  }
}

// /watch media tooling (dev/watch skill). A binary on PATH can still be
// a corpse — a dangling homebrew dylib makes ffmpeg abort at load (dyld,
// exit 134) while `which` stays green — so the native binaries are probed
// with `-version`. yt-dlp is presence-only: probing it costs a Python
// interpreter start for a breakage mode it doesn't have.
export function watchMediaTooling() {
  const missing = [];
  for (const bin of ["ffmpeg", "ffprobe"]) {
    if (!commandExists(bin)) {
      missing.push(bin);
      continue;
    }
    try {
      execSync(`${bin} -version`, {
        stdio: ["pipe", "pipe", "ignore"],
        timeout: 10000,
      });
    } catch {
      missing.push(`${bin} (broken)`);
    }
  }
  if (!commandExists("yt-dlp")) missing.push("yt-dlp");
  return missing;
}

export const checks = [
  {
    name: "install-dir",
    description: "ArkaOS installation directory exists",
    severity: "fail",
    check: () => existsSync(INSTALL_DIR),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "manifest",
    description: "Install manifest present",
    severity: "fail",
    check: () => existsSync(join(INSTALL_DIR, "install-manifest.json")),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "python",
    description: "Python 3.11+ available",
    severity: "fail",
    check: () => {
      const py = getArkaosPython();
      if (!py) return false;
      try {
        const v = execSync(`"${py}" --version 2>&1`, { stdio: "pipe" }).toString();
        const m = v.match(/(\d+)\.(\d+)/);
        return m && parseInt(m[1]) >= 3 && parseInt(m[2]) >= 11;
      } catch { return false; }
    },
    fix: () => "Install Python 3.11+: https://python.org",
  },
  {
    name: "venv",
    // PR2 v3.73.1: promoted from "warn" to "fail" — without the venv, the
    // dashboard cannot start at all (start-dashboard.{sh,ps1} now fail fast
    // instead of falling back to ambient python3 with missing deps).
    description: "ArkaOS virtual environment exists and is runnable",
    severity: "fail",
    check: () => {
      const venvDir = join(INSTALL_DIR, "venv");
      const d = diagnoseVenv(venvDir);
      return d.healthy;
    },
    fix: () => {
      const venvDir = join(INSTALL_DIR, "venv");
      const d = diagnoseVenv(venvDir);
      return `Run: npx arkaos doctor --fix  (current state: ${d.reason})`;
    },
  },
  {
    name: "hooks-dir",
    description: "Hook scripts installed",
    severity: "fail",
    check: () => {
      const required = [
        "session-start",
        "user-prompt-submit",
        "post-tool-use",
        "pre-compact",
        "cwd-changed",
        "pre-tool-use",
        "stop",
        "subagent-stop",
        "session-end",
      ];
      const hooksDir = join(INSTALL_DIR, "config", "hooks");
      return required.every((h) => existsSync(join(hooksDir, `${h}${HOOK_EXT}`)));
    },
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "hook-fastpath",
    description: "Hook fast-path shims consistent (F2-6)",
    severity: "fail",
    check: () => {
      // Only meaningful when the .cjs shims are deployed (POSIX installs
      // from v4.14+). If they are, the manifest + engine + a node binary
      // must exist, or every PreToolUse/PostToolUse fires a dead command
      // that silently fails open — governance off with a green doctor.
      if (IS_WINDOWS) return true;
      const hooksDir = join(INSTALL_DIR, "config", "hooks");
      const shims = ["pre-tool-use.cjs", "post-tool-use.cjs"]
        .map((f) => join(hooksDir, f));
      if (!shims.some((p) => existsSync(p))) return true; // .sh-only install
      if (!shims.every((p) => existsSync(p))) return false; // partial deploy
      if (!existsSync(join(hooksDir, "gate-manifest.json"))) return false;
      if (!existsSync(join(hooksDir, "_lib", "fastpath", "engine.cjs"))) {
        return false;
      }
      return commandExists("node");
    },
    fix: () =>
      "Run: npx arkaos@latest update  (or export ARKA_HOOK_FASTPATH=0 to force the bash chain)",
  },
  {
    name: "arka-tools-runner",
    description: "arka-tools MCP server runnable (uv or venv with mcp SDK)",
    severity: "warn",
    check: () => {
      // Deploy dir + at least one runner. WARN, never FAIL: uv OR a
      // venv with the mcp extra is enough, and neither is mandatory
      // for the core install (F2-7a, `npx arkaos mcp start`).
      const toolsDir = join(
        homedir(), ".claude", "skills", "arka", "mcp-tools");
      if (!existsSync(join(toolsDir, "server.py"))) return false;
      if (commandExists("uv")) return true;
      const py = getArkaosPython();
      if (!py) return false;
      try {
        // timeout parity with mcp-runner.js::venvHasMcp — a hung
        // interpreter must not stall `npx arkaos doctor` (QG 7a M3).
        execSync(`"${py}" -c "import mcp"`, { stdio: "ignore", timeout: 15000 });
        return true;
      } catch {
        return false;
      }
    },
    fix: () =>
      "Install uv (https://docs.astral.sh/uv) or: ~/.arkaos/venv/bin/pip install 'mcp[cli]>=1.2.0' — then: npx arkaos mcp start",
  },
  {
    name: "skills-surface",
    description: "Deployed skill set matches the chosen mode (curated/full)",
    severity: "warn",
    check: () => {
      // WARN-only classifier — the doctor NEVER deletes skills. Repo
      // sub-skills outside the curated cut are "plugin-eligible"
      // leftovers on a curated-mode machine; anything not in the
      // generated skills-manifest (ecosystem skills like user project
      // packs) is unknown/user and untouchable by construction.
      let mode = "full";
      try {
        mode = JSON.parse(readFileSync(
          join(INSTALL_DIR, "skills-mode.json"), "utf-8")).mode || "full";
      } catch {}
      if (mode !== "curated") return true;
      const repoRoot = getRepoRoot();
      if (!repoRoot) return true;
      let manifest;
      try {
        manifest = JSON.parse(readFileSync(
          join(repoRoot, "knowledge", "skills-manifest.json"), "utf-8"));
      } catch {
        return true; // older core without the manifest — nothing to judge
      }
      const skillsBase = join(homedir(), ".claude", "skills");
      let leftovers = 0;
      try {
        for (const dir of readdirSync(skillsBase)) {
          if (!dir.startsWith("arka-")) continue;
          const slug = dir.slice("arka-".length);
          const entry = manifest.skills ? manifest.skills[slug] : null;
          if (entry && !entry.curated) leftovers++;
        }
      } catch {
        return true;
      }
      return leftovers === 0;
    },
    fix: () =>
      "Curated mode with plugin-eligible leftovers deployed (harmless, uses context budget). Install packs a la carte (/plugin install arkaos-<dept>@arkaos) or keep everything: npx arkaos update --skills full",
  },
  {
    name: "constitution",
    description: "Constitution YAML present",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "config", "constitution.yaml")),
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "repo-path",
    description: "Python core reachable (.repo-path or ~/.arkaos/lib snapshot)",
    severity: "warn",
    check: () => {
      // The stable snapshot keeps arka-py working even after
      // `npm cache clean` purges the npx dir .repo-path points at.
      if (existsSync(join(INSTALL_DIR, "lib", "core", "sync", "__init__.py"))) {
        return true;
      }
      const p = join(INSTALL_DIR, ".repo-path");
      if (!existsSync(p)) return false;
      const root = readFileSync(p, "utf-8").trim();
      return existsSync(join(root, "core", "sync", "__init__.py"));
    },
    fix: () => "Run: npx arkaos@latest update (recreates the ~/.arkaos/lib core snapshot)",
  },
  {
    name: "profile",
    description: "User profile exists",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "profile.json")),
    fix: () => "Run: npx arkaos install",
  },
  {
    name: "python-core",
    description: "Python core engine importable",
    severity: "warn",
    check: () => canImportCore(),
    fix: () => {
      const py = getArkaosPython();
      const root = getRepoRoot();
      if (py && root) {
        return `Run: "${py}" -m pip install -e "${root}"`;
      }
      return "Run: npx arkaos@latest update (reinstalls Python core)";
    },
  },
  {
    name: "scheduler",
    description: "Cognitive scheduler config deployed",
    severity: "warn",
    check: () => existsSync(join(INSTALL_DIR, "schedules.yaml")),
    fix: () => "Run: npx arkaos@latest update (deploys scheduler)",
  },
  {
    name: "obsidian",
    description: "Obsidian app installed",
    severity: "warn",
    check: () => checkObsidian().installed,
    fix: () => {
      const s = checkObsidian();
      if (s.suggestedCommand) return `Run: ${s.suggestedCommand}`;
      return `Install Obsidian from ${s.fallbackUrl || "https://obsidian.md/download"}`;
    },
  },
  {
    name: "node",
    description: "Node.js 20+ available",
    severity: "warn",
    check: () => checkNode().needsAction === "none",
    fix: () => {
      const s = checkNode();
      if (s.suggestedCommand) return `Run: ${s.suggestedCommand}`;
      return `Install Node.js 20+ from ${s.fallbackUrl || "https://nodejs.org/en/download"}`;
    },
  },
  {
    name: "ollama",
    description: "Ollama present (optional — cognitive layer LLM runtime)",
    severity: "warn",
    minProfile: "local-ai",
    check: () => checkOllama().installed,
    fix: () => {
      const s = checkOllama();
      if (s.needsAction === "start") return `Run: ${s.suggestedCommand}`;
      if (s.suggestedCommand) return `Run: ${s.suggestedCommand}`;
      return `Install Ollama from ${s.fallbackUrl || "https://ollama.com/download"}`;
    },
  },
  {
    name: "claude-code-version",
    description: "Claude Code 2.1.122+ (ToolSearch late-binding + hooks isolation)",
    severity: "warn",
    check: () => {
      if (!commandExists("claude")) return true; // no claude binary = not applicable
      try {
        const out = execSync("claude --version 2>&1", {
          stdio: "pipe",
        }).toString().trim();
        const m = out.match(/(\d+)\.(\d+)\.(\d+)/);
        if (!m) return false;
        const [, maj, min, patch] = m.map(Number);
        // 2.1.122 minimum
        if (maj > 2) return true;
        if (maj < 2) return false;
        if (min > 1) return true;
        if (min < 1) return false;
        return patch >= 122;
      } catch {
        return false;
      }
    },
    fix: () => "Upgrade Claude Code: npm install -g @anthropic-ai/claude-code@latest",
  },
  {
    name: "graphify",
    description: "Graphify CLI present (grounding layer — code knowledge graphs)",
    severity: "warn",
    check: () => graphifyDoctor().installed,
    fix: () => graphifyDoctor().hint || "Run: uv tool install graphifyy  (or pipx install graphifyy)",
  },
  {
    name: "codebase-memory",
    description: "codebase-memory-mcp binary present (default consistency layer for code stacks)",
    severity: "warn",
    check: () => commandExists("codebase-memory-mcp"),
    fix: () => "Install codebase-memory-mcp (see mcps/registry.json entry for the one-liner), then /arka update to activate per project",
  },
  {
    name: "sqlite-corrupt-backups",
    description: "No self-healed SQLite stores awaiting inspection",
    severity: "warn",
    check: () => corruptDbBackups().length === 0,
    fix: () => "Inspect then delete ~/.arkaos/**/*.corrupt-*.bak",
  },
  {
    name: "magic-api-key",
    description: "Magic API key configured (frontend UI/UX — Magic MCP)",
    severity: "warn",
    check: () => {
      if (process.env.MAGIC_API_KEY) return true;
      const keysPath = join(INSTALL_DIR, "keys.json");
      if (!existsSync(keysPath)) return false;
      try {
        const keys = JSON.parse(readFileSync(keysPath, "utf-8"));
        return !!keys.MAGIC_API_KEY;
      } catch { return false; }
    },
    fix: () => "Run: npx arkaos keys set MAGIC_API_KEY <your-21st-dev-key>  (or re-run npx arkaos@latest update)",
  },
  // ─── Content production prerequisites (PR-C2) — all warn-only:
  // video production is opt-in; the installer never fails on these and
  // never installs the binaries itself (detect + instruct only).
  {
    name: "node-22-video",
    description: "Node.js 22+ (required by Hyperframes video rendering)",
    severity: "warn",
    check: () => {
      const major = parseInt(process.version.slice(1).split(".")[0], 10);
      return Number.isFinite(major) && major >= 22;
    },
    fix: () => "Install Node.js 22+ (nvm install 22) — only needed for /content video rendering",
  },
  {
    name: "ffmpeg",
    description: "FFmpeg present (video encode/cut for Hyperframes + transcription workflows)",
    severity: "warn",
    minProfile: "complete",
    check: () => commandExists("ffmpeg"),
    fix: () => "Install FFmpeg: brew install ffmpeg (macOS) / apt install ffmpeg (Linux) / winget install Gyan.FFmpeg (Windows)",
  },
  {
    name: "agent-reach",
    description: "Agent-Reach CLI present (multi-platform source pulls for the content trend and research skills)",
    severity: "warn",
    check: () => commandExists("agent-reach"),
    fix: () => 'Not on PyPI — install from the third-party GitHub repo (confirm the source first): uv tool install "git+https://github.com/Panniantong/Agent-Reach", then run: agent-reach doctor',
  },
  {
    name: "hyperframes-skills",
    description: "Hyperframes skills installed (video-as-code editing for /content video)",
    severity: "warn",
    check: () => hyperframesSkillsInstalled(),
    fix: () => "Run /content video-setup in Claude Code, or: npx skills add heygen-com/hyperframes --full-depth --yes",
  },
  {
    name: "higgsfield-api-key",
    description: "Higgsfield API key configured (image/video/audio generation engine)",
    severity: "warn",
    check: () => {
      if (process.env.HIGGSFIELD_API_KEY) return true;
      const keysPath = join(INSTALL_DIR, "keys.json");
      if (!existsSync(keysPath)) return false;
      try {
        const keys = JSON.parse(readFileSync(keysPath, "utf-8"));
        return !!keys.HIGGSFIELD_API_KEY;
      } catch { return false; }
    },
    fix: () => "Run: npx arkaos keys set HIGGSFIELD_API_KEY <key> (https://higgsfield.ai) — needed for Higgsfield MCP generation",
  },
  // ─── Claude-layer checks (issue #358) — migrated from the bash doctor.
  // All warn-only: ArkaOS is multi-runtime, so absence of the Claude
  // surface must never fail an install that targets codex/gemini/cursor.
  {
    name: "claude-cli",
    description: "Claude Code CLI installed",
    severity: "warn",
    check: () => commandExists("claude"),
    fix: () => "Install: npm install -g @anthropic-ai/claude-code (or use another supported runtime)",
  },
  {
    name: "arka-skill",
    description: "arka orchestrator skill bundle deployed (~/.claude/skills/arka)",
    severity: "warn",
    check: () =>
      existsSync(join(homedir(), ".claude", "skills", "arka", "SKILL.md")),
    fix: () => "Run: npx arkaos install --force",
  },
  {
    name: "jq",
    description: "jq available (bash hooks parse JSON with it; python3 is the fallback)",
    severity: "warn",
    check: () => commandExists("jq"),
    fix: () => "Install jq: brew install jq (macOS) / apt install jq (Linux)",
  },
  {
    name: "statusline",
    description: "Status line configured and its command exists",
    severity: "warn",
    check: () => statuslineConfigured(),
    fix: () => "Run: npx arkaos install --force (redeploys and wires the statusline)",
  },
  {
    name: "autoupdate",
    description: "Auto-update daemon installed (or explicit user opt-out)",
    severity: "warn",
    check: () => {
      const s = autoupdateStatus();
      return !s.supported || s.optout || s.installed;
    },
    fix: () => "Run: npx arkaos autoupdate enable",
  },
  {
    name: "hooks-wired",
    description: "Hook chain referenced by ~/.claude/settings.json (governance live)",
    severity: "warn",
    check: () => hooksWired(),
    fix: () => "Run: npx arkaos install --force (rewires hooks into settings.json)",
  },
  {
    name: "skills-deployed",
    description: "ArkaOS skill set deployed (>= 7 arka-* skills)",
    severity: "warn",
    check: () => deployedSkillCount() >= 7,
    fix: () => "Run: npx arkaos@latest update (redeploys the curated skill set)",
  },
  {
    name: "mcp-registry",
    description: "MCP registry present in the arka skill bundle",
    severity: "warn",
    check: () => mcpRegistryHealthy(),
    fix: () => "Run: npx arkaos install --force",
  },
  {
    // Supersedes the presence-only "yt-dlp" check: dev/watch needs
    // ffmpeg/ffprobe too, and needs them RUNNABLE, not just on PATH.
    name: "watch-media-tooling",
    description: "/watch video tooling (ffmpeg, ffprobe, yt-dlp) present and runnable",
    severity: "warn",
    check: () => watchMediaTooling().length === 0,
    fix: () => {
      const missing = watchMediaTooling();
      return (
        `Missing/broken: ${missing.join(", ")}. macOS: brew install ffmpeg yt-dlp ` +
        "(a (broken) entry usually means a dangling dylib — brew reinstall it). " +
        "Or run the dev/watch installer: ~/.claude/skills/arka-watch/scripts/setup.py"
      );
    },
  },
  {
    name: "gotchas",
    description: "gotchas.json valid (capture layer output, ingested by /arka evolve)",
    severity: "warn",
    check: () => gotchasHealthy(),
    fix: () => "Missing: capture has not run yet (created automatically). Corrupt: inspect ~/.arkaos/gotchas.json — /arka evolve cannot ingest it",
  },
  {
    name: "companion-plugins",
    description: "Companion plugins installed (Superpowers + Claude-Mem)",
    severity: "warn",
    check: () => companionPluginsInstalled(),
    fix: () => "claude plugin marketplace add obra/superpowers-marketplace && claude plugin install superpowers@superpowers-marketplace; claude plugin marketplace add thedotmack/claude-mem && claude plugin install claude-mem@thedotmack",
  },
  // ─── Install-profile checks (Foundation PR-4) — all warn-only ─────────
  {
    name: "install-profile",
    description: "Install profile valid (profile.json + install-profiles manifest)",
    severity: "warn",
    check: () => {
      // A profile.json that predates PR-3 (no installProfile key) is
      // valid — it means essential. An explicitly invalid value or an
      // unloadable/unresolvable manifest is the failure.
      const profilePath = join(INSTALL_DIR, "profile.json");
      if (existsSync(profilePath)) {
        try {
          const profile = JSON.parse(readFileSync(profilePath, "utf-8"));
          if (
            profile.installProfile !== undefined &&
            !normalizeProfileFlag(profile.installProfile)
          ) {
            return false;
          }
        } catch {
          return false;
        }
      }
      const repoRoot = getRepoRoot();
      if (!repoRoot) return true; // no repo reference — not a profile problem
      try {
        const manifest = loadProfilesManifest(repoRoot);
        resolveServicesForProfile(currentInstallProfile(), manifest);
        return true;
      } catch {
        return false;
      }
    },
    fix: () =>
      "profile.json installProfile must be one of essential|complete|local-ai; refresh the manifest via: npx arkaos@latest update",
  },
  {
    name: "litellm-proxy",
    description: "LiteLLM proxy installed (gateway prerequisite — complete profile)",
    severity: "warn",
    minProfile: "complete",
    check: () => {
      const py = getArkaosPython();
      if (!py) return false;
      try {
        execSync(`"${py}" -c "import litellm"`, { stdio: "ignore", timeout: 30000 });
        return true;
      } catch {
        return false;
      }
    },
    fix: () =>
      "Run: ~/.arkaos/venv/bin/pip install 'litellm[proxy]'  (or: npx arkaos doctor --fix)",
  },
  {
    name: "whisper",
    description: "Whisper transcription installed (faster-whisper — complete profile)",
    severity: "warn",
    minProfile: "complete",
    check: () => {
      const py = getArkaosPython();
      if (!py) return false;
      try {
        execSync(`"${py}" -c "import faster_whisper"`, { stdio: "ignore", timeout: 30000 });
        return true;
      } catch {
        return false;
      }
    },
    fix: () =>
      "Run: ~/.arkaos/venv/bin/pip install faster-whisper  (or: npx arkaos doctor --fix)",
  },
  {
    name: "ollama-execution-model",
    description: "Local execution model pulled (Model Fabric — local-ai profile)",
    severity: "warn",
    minProfile: "local-ai",
    check: () => {
      const resolved = parseExecutionModel();
      // No ollama execution role in models.yaml — nothing to verify.
      if (!resolved) return true;
      try {
        const out = execSync("ollama list", {
          stdio: ["ignore", "pipe", "ignore"],
          timeout: 10000,
        }).toString();
        return out.split(/\r?\n/).some((line) => {
          const token = line.trim().split(/\s+/)[0];
          return (
            token === resolved.model ||
            (!resolved.model.includes(":") && token.split(":")[0] === resolved.model)
          );
        });
      } catch {
        return false;
      }
    },
    fix: () => {
      const resolved = parseExecutionModel();
      return resolved
        ? `Run: ollama pull ${resolved.model}  (or: npx arkaos doctor --fix)`
        : "Configure: npx arkaos models set execution ollama/<model>";
    },
  },
];

// ─── Windows-only checks ───────────────────────────────────────────────
// Appended conditionally so non-Windows runs are byte-for-byte unchanged.
if (IS_WINDOWS) {
  checks.push(
    {
      name: "powershell",
      description: "PowerShell 5.1+ available",
      severity: "fail",
      check: () => {
        try {
          const out = execSync(
            'powershell -NoProfile -Command "$PSVersionTable.PSVersion.Major"',
            { stdio: ["pipe", "pipe", "ignore"] }
          ).toString().trim();
          const major = parseInt(out, 10);
          return Number.isFinite(major) && major >= 5;
        } catch {
          return false;
        }
      },
      fix: () => "Install Windows PowerShell 5.1+ (ships with every Windows 10/11).",
    },
    {
      name: "arka-claude-wrapper",
      description: "arka-claude wrapper installed (.cmd + .ps1)",
      severity: "warn",
      check: () =>
        existsSync(join(INSTALL_DIR, "bin", "arka-claude.cmd")) &&
        existsSync(join(INSTALL_DIR, "bin", "arka-claude.ps1")),
      fix: () => "Run: npx arkaos install --force",
    },
    {
      name: "schtasks",
      description: "schtasks available (cognitive scheduler backend)",
      severity: "warn",
      check: () => commandExists("schtasks"),
      fix: () => "schtasks ships with Windows by default; verify %WINDIR%\\System32 is on PATH.",
    },
    {
      name: "venv-scripts",
      description: "Venv Python at %USERPROFILE%\\.arkaos\\venv\\Scripts\\python.exe",
      severity: "warn",
      check: () => {
        const venvPy = getVenvPython();
        // Only meaningful if venv exists at all. The "venv" check above
        // covers absence; this one guards against a macOS-shaped venv
        // being mistaken for a Windows venv (bin/ instead of Scripts/).
        if (!existsSync(join(INSTALL_DIR, "venv"))) return true;
        return existsSync(venvPy) && venvPy.toLowerCase().endsWith("\\scripts\\python.exe");
      },
      fix: () => "Remove %USERPROFILE%\\.arkaos\\venv and run: npx arkaos@latest update",
    }
  );
}

export async function doctor(options = {}) {
  const fixMode = !!options.fix;
  const jsonMode = !!options.json;
  if (jsonMode) return doctorJson();
  console.log(`\n  ArkaOS Doctor — Health Checks${fixMode ? " (--fix)" : ""}\n`);

  // ─── --fix: repair the venv before reporting checks (PR2 v3.73.1) ────
  // Targeted, idempotent self-heal: detects broken symlinks / version
  // drift / missing bin/python and recreates the venv with --clear so
  // the subsequent venv check has a chance of passing.
  if (fixMode) {
    const venvDir = join(INSTALL_DIR, "venv");
    const before = diagnoseVenv(venvDir);
    if (before.healthy) {
      console.log("  ℹ Venv already healthy — no repair needed");
    } else {
      console.log(`  → Repairing venv (current state: ${before.reason})`);
      const result = ensureVenvHealthy({
        venvDir,
        log: (msg) => console.log("    " + msg.trim()),
      });
      if (result.healthy && result.repaired) {
        console.log("  ✓ Venv repaired");
      } else if (!result.healthy) {
        console.log(`  ✗ Venv repair failed (${result.reason})`);
      }
    }

    // ─── --fix: reconcile the install profile's services (PR-4) ──────
    // Non-interactive: consent-free services (pip into our venv, model
    // pull) install; consent-gated ones print the exact command. Never
    // blocks — a reconcile error degrades to a single warning line.
    try {
      const repoRoot = getRepoRoot();
      if (repoRoot) {
        const activeProfile = currentInstallProfile();
        console.log(`  → Reconciling ${activeProfile} profile services`);
        const { reconcileServices } = await import("./services.js");
        const results = await reconcileServices({
          profile: activeProfile,
          repoRoot,
          interactive: false,
          log: (msg) => console.log("    " + String(msg).trim()),
        });
        for (const r of results) {
          if (r.status === "installed") console.log(`  ✓ ${r.label} installed`);
          else if (r.status === "failed") console.log(`  ✗ ${r.label} failed${r.hint ? ` — ${r.hint}` : ""}`);
          else if (r.status === "skipped") console.log(`  · ${r.label} skipped${r.hint ? ` — ${r.hint}` : ""}`);
        }
      }
    } catch (err) {
      console.log(`  ⚠ Service reconciliation skipped (${err.message})`);
    }
    console.log("");
  }

  const activeProfile = currentInstallProfile();
  let passed = 0;
  let warned = 0;
  let failed = 0;
  let skipped = 0;

  for (const check of checks) {
    // Profile gate (PR-4): below-profile checks are informational
    // skips, not warnings — see checkSkipReason.
    const skipReason = checkSkipReason(check, activeProfile);
    if (skipReason) {
      console.log(`  \x1b[90m-\x1b[0m  ${check.description} — skipped (${skipReason})`);
      skipped++;
      continue;
    }
    // A single check that throws must not crash the rest of the doctor.
    // Treat the exception as "check failed" and record a short hint so
    // the user can see what blew up. Also keep any stack-trace noise
    // out of the console output.
    let ok = false;
    let checkError = null;
    try {
      ok = !!check.check();
    } catch (err) {
      checkError = err && err.message ? String(err.message).split("\n")[0].slice(0, 120) : String(err);
    }

    const icon = ok
      ? "\x1b[32m\u2713\x1b[0m"
      : (check.severity === "fail" ? "\x1b[31m\u2717\x1b[0m" : "\x1b[33m!\x1b[0m");
    console.log(`  ${icon}  ${check.description}`);

    if (!ok) {
      if (checkError) {
        console.log(`     Error: ${checkError}`);
      }
      let fixHint;
      try {
        fixHint = check.fix();
      } catch (err) {
        fixHint = "(fix hint unavailable)";
      }
      console.log(`     Fix: ${fixHint}`);
      if (check.severity === "fail") failed++;
      else warned++;
    } else {
      passed++;
    }
  }

  const skippedSuffix = skipped > 0 ? `, ${skipped} skipped` : "";
  console.log(`\n  Results: ${passed} passed, ${warned} warnings, ${failed} failures${skippedSuffix}\n`);
  await securityAdvisory();
  if (failed > 0) process.exit(1);
}

// Machine-readable run (issue #358 step 4). Same checks, same exit-code
// contract as the human run; the security advisory stays out — it is a
// human-facing print, and the scanner already has its own --json
// (core.governance.harness_scanner_cli).
function doctorJson() {
  const results = [];
  const activeProfile = currentInstallProfile();
  let passed = 0;
  let warned = 0;
  let failed = 0;
  let skipped = 0;
  for (const check of checks) {
    // Profile gate (PR-4) — same skip semantics as the human run.
    const skipReason = checkSkipReason(check, activeProfile);
    if (skipReason) {
      skipped++;
      results.push({
        name: check.name,
        status: "skipped",
        severity: check.severity,
        description: check.description,
        fix: "",
        skipReason,
      });
      continue;
    }
    let ok = false;
    let error = null;
    try {
      ok = !!check.check();
    } catch (err) {
      error = err && err.message
        ? String(err.message).split("\n")[0].slice(0, 120)
        : String(err);
    }
    const status = ok ? "pass" : check.severity === "fail" ? "fail" : "warn";
    if (ok) passed++;
    else if (check.severity === "fail") failed++;
    else warned++;
    const entry = {
      name: check.name,
      status,
      severity: check.severity,
      description: check.description,
      fix: ok ? "" : safeFix(check),
    };
    if (error) entry.error = error;
    results.push(entry);
  }
  console.log(JSON.stringify({
    checks: results,
    summary: { passed, warned, failed, skipped, total: results.length },
  }));
  if (failed > 0) process.exit(1);
}

function safeFix(check) {
  try {
    return check.fix();
  } catch {
    return "(fix hint unavailable)";
  }
}

// Doctor answers "is the install healthy?". It never answered "is the
// install SAFE?" — a config can be perfectly healthy and still hand a
// third party the right to run code on this machine. The scanner does
// that, and doctor is where the operator already looks.
//
// Advisory only: it prints the grade and never changes doctor's exit
// code. A health check that starts failing on a pre-existing security
// posture would be a breaking change to everyone's CI, and the way to
// get a security tool ignored is to make it block on day one.
async function securityAdvisory() {
  const python = getArkaosPython();
  const repoRoot = getRepoRoot();
  if (!python || !repoRoot) return;
  const { spawnSync } = await import("node:child_process");
  const run = spawnSync(
    python,
    ["-m", "core.governance.harness_scanner_cli", "--json"],
    {
      encoding: "utf-8",
      cwd: process.cwd(),
      env: { ...process.env, ARKAOS_ROOT: repoRoot, PYTHONPATH: repoRoot },
    }
  );
  // A crash must not read as "clean". If the scanner did not return a
  // parseable report, say so — the same crash-is-not-clean rule the
  // scanner enforces internally.
  let report = null;
  if (run.status !== null && run.stdout) {
    try { report = JSON.parse(run.stdout); } catch { report = null; }
  }
  if (!report || !Array.isArray(report.findings)) {
    console.log("  Security: scan did not complete — run `npx arkaos shield` directly\n");
    return;
  }

  const cross = process.stdout.isTTY ? "\x1b[31m✗\x1b[0m" : "x";
  const n = report.findings.length;
  const plural = n === 1 ? "finding" : "findings";
  console.log(`  Security: grade ${report.grade} (${report.score}/100), ${n} ${plural}`);
  for (const finding of report.findings.filter((f) => f.severity === "critical").slice(0, 3)) {
    console.log(`     ${cross} ${finding.rule} — ${finding.where}`);
  }
  console.log(n > 0 ? "     Run: npx arkaos shield\n" : "");
}
