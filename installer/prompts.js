/**
 * Interactive prompts for ArkaOS installer.
 * Asks user for directories, language, market, preferences.
 * Nothing is hardcoded — everything comes from the user.
 *
 * Foundation PR-3: the wizard renders through @clack/prompts when the
 * terminal supports it (see installer/ui.js) and falls back to the
 * original readline flow otherwise. Both paths return the same config
 * shape, now including `installProfile` (persisted by index.js;
 * provisioning of the non-essential tiers is PR-4).
 */

import { createInterface } from "node:readline";
import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import { getUi } from "./ui.js";
import {
  DEFAULT_PROFILE,
  INSTALL_PROFILES,
  PROFILE_HINTS,
  normalizeProfileFlag,
} from "./profile.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const VERSION = JSON.parse(
  readFileSync(join(__dirname, "..", "package.json"), "utf-8"),
).version;

// Readline interface is lazily created so headless upgrade runs can
// return without ever opening stdin. Eagerly constructing the interface
// at module import caused `npx arkaos install --force` to block on a
// closed-stdin pipe even when the wizard short-circuited below.
let rl = null;
function getRl() {
  if (!rl) {
    rl = createInterface({ input: process.stdin, output: process.stdout });
  }
  return rl;
}

function ask(question, defaultValue = "") {
  const suffix = defaultValue ? ` [${defaultValue}]` : "";
  return new Promise((resolve) => {
    getRl().question(`  ${question}${suffix}: `, (answer) => {
      resolve(answer.trim() || defaultValue);
    });
  });
}

function askYN(question, defaultYes = true) {
  const suffix = defaultYes ? " [Y/n]" : " [y/N]";
  return new Promise((resolve) => {
    getRl().question(`  ${question}${suffix}: `, (answer) => {
      const a = answer.trim().toLowerCase();
      if (!a) resolve(defaultYes);
      else resolve(a === "y" || a === "yes");
    });
  });
}

function askChoice(question, options) {
  return new Promise((resolve) => {
    console.log(`  ${question}`);
    options.forEach((opt, i) => {
      console.log(`    ${i + 1}) ${opt.label}`);
    });
    getRl().question(`  Choose [1-${options.length}]: `, (answer) => {
      const idx = parseInt(answer.trim()) - 1;
      if (idx >= 0 && idx < options.length) {
        resolve(options[idx].value);
      } else {
        resolve(options[0].value); // Default to first
      }
    });
  });
}

// Canonical ArkaOS data directory. Mirrors the fallback used at the
// top of installer/index.js::install so headless upgrade detection
// can reach the existing profile.json before the wizard tries to ask
// the user where their install lives.
const DEFAULT_INSTALL_DIR = join(homedir(), ".arkaos");

// Shared option lists — one source for both the clack and readline wizards.
const LANGUAGE_OPTIONS = [
  { label: "English", value: "en" },
  { label: "Português", value: "pt" },
  { label: "Español", value: "es" },
  { label: "Français", value: "fr" },
  { label: "Deutsch", value: "de" },
  { label: "Italiano", value: "it" },
  { label: "中文 (Chinese)", value: "zh" },
  { label: "日本語 (Japanese)", value: "ja" },
  { label: "한국어 (Korean)", value: "ko" },
  { label: "Other", value: "other" },
];

const ROLE_OPTIONS = [
  { label: "Developer / Engineer", value: "developer" },
  { label: "Founder / CEO", value: "founder" },
  { label: "Marketing / Growth", value: "marketing" },
  { label: "Product Manager", value: "product" },
  { label: "Designer", value: "designer" },
  { label: "Consultant / Agency", value: "consultant" },
  { label: "Other", value: "other" },
];

const PROFILE_OPTIONS = INSTALL_PROFILES.map((value) => ({
  value,
  label: value,
  hint: PROFILE_HINTS[value],
}));

// When called on an upgrade and a valid profile.json already exists,
// honor the rule documented in .claude/rules/node-installer.md:
//
//     No interactive prompts during headless/CI runs
//
// An upgrade by definition means the user already answered these
// questions on a prior install, so re-asking every field (language,
// market, role, company, project dir, vault, feature flags, keys)
// blocks `npx arkaos install --force` even from a redirected-stdin
// context like `/dev/null` or CI. readline reads directly from
// process.stdin and does not honor those redirects.
//
// The short-circuit reads the existing profile and returns a config
// compatible with installer/index.js::install's downstream expectations:
//
//   - User metadata fields (language, market, role, company,
//     projectsDir, vaultPath) come from profile.json.
//   - installProfile is carried from profile.json when present and
//     valid; older profiles without the field default to "essential"
//     (Foundation PR-3 — the profile only gates provisioning in PR-4,
//     so defaulting is safe for existing installs).
//   - installDir is the directory we found the profile in.
//   - Feature flags (installDashboard, installKnowledge,
//     installTranscription) default to false on upgrade — an upgrade
//     should NOT reinstall optional features; if the user wants to
//     add one, they re-run a fresh install with the wizard. This
//     preserves the existing install exactly.
//   - API key fields are left empty; keys live in keys.json and the
//     installer already merges them non-destructively.
//
// Returns null when the short-circuit conditions are not met, which
// falls through to the interactive wizard below (fresh install or
// upgrade with a corrupt/missing profile).
export function loadExistingProfileConfig(installDir) {
  const profilePath = join(installDir, "profile.json");
  if (!existsSync(profilePath)) return null;
  try {
    const profile = JSON.parse(readFileSync(profilePath, "utf-8"));
    // Require the fields the downstream installer flow actually uses.
    // Any missing field forces the wizard so we never write a
    // half-populated profile back to disk on upgrade.
    if (!profile.language || !profile.role) return null;
    return {
      language: profile.language,
      market: profile.market || "",
      role: profile.role,
      company: profile.company || "",
      projectsDir: profile.projectsDir || join(homedir(), "Projects"),
      vaultPath: profile.vaultPath || "",
      installDir,
      installProfile:
        normalizeProfileFlag(profile.installProfile) || DEFAULT_PROFILE,
      // Upgrades preserve the existing install footprint; they do not
      // re-opt-in to optional features. A user who wants to flip a
      // feature flag on upgrade can re-run with the wizard.
      // Exception: knowledge deps are always installed on upgrade because
      // they are required for `npx arkaos index/search` to use vector
      // search instead of degraded keyword fallback.
      installDashboard: false,
      installKnowledge: true,
      installTranscription: false,
      openaiKey: "",
      googleKey: "",
      falKey: "",
    };
  } catch {
    // Corrupt profile.json — fall through to the wizard so the user
    // has a path to fix it.
    return null;
  }
}

export async function runSetupPrompts(isUpgrade = false, opts = {}) {
  // Headless upgrade short-circuit. See loadExistingProfileConfig.
  if (isUpgrade) {
    const existing = loadExistingProfileConfig(DEFAULT_INSTALL_DIR);
    if (existing) {
      console.log(`
  ╔══════════════════════════════════════════════════════╗
  ║  ArkaOS Upgrade — using existing profile            ║
  ╚══════════════════════════════════════════════════════╝

    Language:       ${existing.language}
    Market:         ${existing.market || "(not set)"}
    Role:           ${existing.role}
    Company:        ${existing.company || "(not set)"}
    Install dir:    ${existing.installDir}
    Profile:        ${existing.installProfile}

    Optional features are NOT re-installed on upgrade.
    Re-run without --force to flip feature flags interactively.
  `);
      return existing;
    }
  }

  // A valid --profile flag skips the profile question in both wizards.
  const profileFlag = normalizeProfileFlag(opts.profileFlag);

  const ui = await getUi();
  if (ui.isFancy()) {
    return runClackWizard(ui, profileFlag);
  }
  return runReadlineWizard(profileFlag);
}

// ── Fancy wizard (@clack/prompts) ─────────────────────────────────────────

async function runClackWizard(ui, profileFlag) {
  const p = ui.clack;
  const pc = ui.colors;

  // Ctrl+C anywhere cancels the whole install, mirroring the readline
  // wizard's "Installation cancelled." exit.
  const guard = (value) => {
    if (p.isCancel(value)) {
      p.cancel("Installation cancelled.");
      process.exit(0);
    }
    return value;
  };

  p.intro(pc.inverse(pc.bold(` ▲ ARKA OS v${VERSION} — Setup `)));

  const config = {};

  // ── Identity ──
  p.log.step(pc.bold("Identity"));
  config.language = guard(
    await p.select({
      message: "What is your primary language?",
      options: LANGUAGE_OPTIONS.map(({ label, value }) => ({ value, label })),
      initialValue: "en",
    }),
  );
  if (config.language === "other") {
    config.language =
      String(
        guard(
          await p.text({
            message: "Enter language code",
            placeholder: "e.g., nl, pl, ru",
          }),
        ) || "",
      ).trim() || "en";
  }
  config.market = String(
    guard(
      await p.text({
        message: "What is your primary market/country?",
        placeholder: "e.g., United States, Portugal, Global",
      }),
    ) || "",
  ).trim();
  config.role = guard(
    await p.select({
      message: "What best describes your role?",
      options: ROLE_OPTIONS.map(({ label, value }) => ({ value, label })),
      initialValue: "developer",
    }),
  );
  config.company = String(
    guard(
      await p.text({
        message: "Company or organization name (optional)",
        defaultValue: "",
      }),
    ) || "",
  ).trim();

  // ── Directories ──
  p.log.step(pc.bold("Directories"));
  config.projectsDir =
    String(
      guard(
        await p.text({
          message: "Where are your projects?",
          initialValue: join(homedir(), "Projects"),
        }),
      ) || "",
    ).trim() || join(homedir(), "Projects");
  config.vaultPath = String(
    guard(
      await p.text({
        message: "Where is your Obsidian vault? (leave empty if none)",
        defaultValue: "",
      }),
    ) || "",
  ).trim();
  if (config.vaultPath && !existsSync(config.vaultPath)) {
    const create = guard(
      await p.confirm({
        message: `Directory not found: ${config.vaultPath} — create it?`,
        initialValue: false,
      }),
    );
    if (!create) config.vaultPath = "";
  }
  config.installDir =
    String(
      guard(
        await p.text({
          message: "ArkaOS data directory",
          initialValue: DEFAULT_INSTALL_DIR,
        }),
      ) || "",
    ).trim() || DEFAULT_INSTALL_DIR;

  // ── Installation profile ──
  p.log.step(pc.bold("Installation profile"));
  if (profileFlag) {
    config.installProfile = profileFlag;
    p.log.info(`Profile: ${profileFlag} (from --profile)`);
  } else {
    config.installProfile = guard(
      await p.select({
        message: "Which installation profile?",
        options: PROFILE_OPTIONS,
        initialValue: DEFAULT_PROFILE,
      }),
    );
  }

  // ── Optional features ──
  p.log.step(pc.bold("Optional features"));
  config.installDashboard = guard(
    await p.confirm({
      message: "Install monitoring dashboard?",
      initialValue: true,
    }),
  );
  config.installKnowledge = guard(
    await p.confirm({
      message: "Install knowledge base (vector DB)?",
      initialValue: true,
    }),
  );
  config.installTranscription = guard(
    await p.confirm({
      message: "Install audio transcription (Whisper)?",
      initialValue: false,
    }),
  );

  // ── API keys (optional) ──
  p.log.step(pc.bold("API keys (optional, can be configured later)"));
  config.openaiKey = String(
    guard(
      await p.password({
        message: "OpenAI API key (Whisper, embeddings — Enter to skip)",
        mask: "•",
      }),
    ) || "",
  ).trim();
  config.googleKey = String(
    guard(
      await p.password({
        message: "Google API key (Gemini, Nano Banana — Enter to skip)",
        mask: "•",
      }),
    ) || "",
  ).trim();
  config.falKey = String(
    guard(
      await p.password({
        message: "fal.ai API key (image/video generation — Enter to skip)",
        mask: "•",
      }),
    ) || "",
  ).trim();

  // ── Summary + confirm ──
  p.note(formatSummary(config), "Configuration Summary");
  const confirmed = guard(
    await p.confirm({
      message: "Proceed with this configuration?",
      initialValue: true,
    }),
  );
  if (!confirmed) {
    p.cancel("Installation cancelled.");
    process.exit(0);
  }
  p.outro("Configuration complete — installing.");
  return config;
}

// ── Plain wizard (readline fallback) ──────────────────────────────────────

async function runReadlineWizard(profileFlag) {
  console.log(`
  ╔══════════════════════════════════════════════════════╗
  ║  ArkaOS Setup — Let's configure your environment    ║
  ╚══════════════════════════════════════════════════════╝
  `);

  const config = {};

  // ── Language ──
  config.language = await askChoice(
    "What is your primary language?",
    LANGUAGE_OPTIONS,
  );

  if (config.language === "other") {
    config.language = await ask("Enter language code (e.g., nl, pl, ru)");
  }

  // ── Market/Country ──
  config.market = await ask("What is your primary market/country?", "");
  console.log("    (e.g., United States, Portugal, Brazil, Germany, Global)");
  if (!config.market) {
    config.market = await ask("Market/Country");
  }

  // ── Role ──
  config.role = await askChoice("What best describes your role?", ROLE_OPTIONS);

  // ── Company ──
  config.company = await ask("Company or organization name (optional)", "");

  // ── Directories ──
  console.log("\n  ── Directories ──\n");

  config.projectsDir = await ask(
    "Where are your projects?",
    join(homedir(), "Projects")
  );

  config.vaultPath = await ask(
    "Where is your Obsidian vault? (leave empty if none)",
    ""
  );
  if (config.vaultPath && !existsSync(config.vaultPath)) {
    console.log(`    ⚠ Directory not found: ${config.vaultPath}`);
    const create = await askYN("Create it?", false);
    if (!create) config.vaultPath = "";
  }

  config.installDir = await ask(
    "ArkaOS data directory",
    DEFAULT_INSTALL_DIR
  );

  // ── Installation profile ──
  console.log("\n  ── Installation Profile ──\n");

  if (profileFlag) {
    config.installProfile = profileFlag;
    console.log(`  Profile: ${profileFlag} (from --profile)`);
  } else {
    config.installProfile = await askChoice(
      "Which installation profile?",
      PROFILE_OPTIONS.map(({ value, hint }) => ({
        value,
        label: `${value} — ${hint}`,
      })),
    );
  }

  // ── Features ──
  console.log("\n  ── Optional Features ──\n");

  config.installDashboard = await askYN("Install monitoring dashboard?", true);
  config.installKnowledge = await askYN("Install knowledge base (vector DB)?", true);
  config.installTranscription = await askYN("Install audio transcription (Whisper)?", false);

  // ── API Keys (optional) ──
  console.log("\n  ── API Keys (optional, can be configured later) ──\n");

  config.openaiKey = await ask("OpenAI API key (for Whisper, embeddings — leave empty to skip)", "");
  config.googleKey = await ask("Google API key (Gemini, Nano Banana — leave empty to skip)", "");
  config.falKey = await ask("fal.ai API key (image/video generation — leave empty to skip)", "");

  // ── Summary ──
  console.log(`
  ── Configuration Summary ──

${formatSummary(config)
  .split("\n")
  .map((l) => `    ${l}`)
  .join("\n")}
  `);

  const confirmed = await askYN("Proceed with this configuration?", true);
  if (!confirmed) {
    console.log("\n  Installation cancelled.\n");
    rl?.close();
    process.exit(0);
  }

  rl?.close();
  return config;
}

function formatSummary(config) {
  return [
    `Language:       ${config.language}`,
    `Market:         ${config.market || "(not set)"}`,
    `Role:           ${config.role}`,
    `Company:        ${config.company || "(not set)"}`,
    `Projects dir:   ${config.projectsDir}`,
    `Obsidian vault: ${config.vaultPath || "(none)"}`,
    `Install dir:    ${config.installDir}`,
    `Profile:        ${config.installProfile}`,
    `Dashboard:      ${config.installDashboard ? "Yes" : "No"}`,
    `Knowledge DB:   ${config.installKnowledge ? "Yes" : "No"}`,
    `Transcription:  ${config.installTranscription ? "Yes" : "No"}`,
    `OpenAI key:     ${config.openaiKey ? "configured" : "not set"}`,
    `Google key:     ${config.googleKey ? "configured" : "not set"}`,
    `fal.ai key:     ${config.falKey ? "configured" : "not set"}`,
  ].join("\n");
}

export function closePrompts() {
  // rl is only created when the readline wizard actually asked a
  // question; a fancy/clack or short-circuited run leaves it null.
  try { rl?.close(); } catch { /* already closed */ }
}
