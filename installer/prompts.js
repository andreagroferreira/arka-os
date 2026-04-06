/**
 * Interactive prompts for ArkaOS installer.
 * Asks user for directories, language, market, preferences.
 * Nothing is hardcoded — everything comes from the user.
 */

import { createInterface } from "node:readline";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const rl = createInterface({ input: process.stdin, output: process.stdout });

function ask(question, defaultValue = "") {
  const suffix = defaultValue ? ` [${defaultValue}]` : "";
  return new Promise((resolve) => {
    rl.question(`  ${question}${suffix}: `, (answer) => {
      resolve(answer.trim() || defaultValue);
    });
  });
}

function askYN(question, defaultYes = true) {
  const suffix = defaultYes ? " [Y/n]" : " [y/N]";
  return new Promise((resolve) => {
    rl.question(`  ${question}${suffix}: `, (answer) => {
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
    rl.question(`  Choose [1-${options.length}]: `, (answer) => {
      const idx = parseInt(answer.trim()) - 1;
      if (idx >= 0 && idx < options.length) {
        resolve(options[idx].value);
      } else {
        resolve(options[0].value); // Default to first
      }
    });
  });
}

export async function runSetupPrompts(isUpgrade = false) {
  console.log(`
  ╔══════════════════════════════════════════════════════╗
  ║  ArkaOS Setup — Let's configure your environment    ║
  ╚══════════════════════════════════════════════════════╝
  `);

  const config = {};

  // ── Language ──
  config.language = await askChoice("What is your primary language?", [
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
  ]);

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
  config.role = await askChoice("What best describes your role?", [
    { label: "Developer / Engineer", value: "developer" },
    { label: "Founder / CEO", value: "founder" },
    { label: "Marketing / Growth", value: "marketing" },
    { label: "Product Manager", value: "product" },
    { label: "Designer", value: "designer" },
    { label: "Consultant / Agency", value: "consultant" },
    { label: "Other", value: "other" },
  ]);

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
    join(homedir(), ".arkaos")
  );

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

    Language:       ${config.language}
    Market:         ${config.market || "(not set)"}
    Role:           ${config.role}
    Company:        ${config.company || "(not set)"}
    Projects dir:   ${config.projectsDir}
    Obsidian vault: ${config.vaultPath || "(none)"}
    Install dir:    ${config.installDir}
    Dashboard:      ${config.installDashboard ? "Yes" : "No"}
    Knowledge DB:   ${config.installKnowledge ? "Yes" : "No"}
    Transcription:  ${config.installTranscription ? "Yes" : "No"}
    OpenAI key:     ${config.openaiKey ? "configured" : "not set"}
    Google key:     ${config.googleKey ? "configured" : "not set"}
    fal.ai key:     ${config.falKey ? "configured" : "not set"}
  `);

  const confirmed = await askYN("Proceed with this configuration?", true);
  if (!confirmed) {
    console.log("\n  Installation cancelled.\n");
    rl.close();
    process.exit(0);
  }

  rl.close();
  return config;
}

export function closePrompts() {
  try { rl.close(); } catch {}
}
