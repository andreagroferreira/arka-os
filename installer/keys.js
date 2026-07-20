import {
  existsSync, readFileSync, writeFileSync, chmodSync, renameSync, unlinkSync,
} from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const KEYS_PATH = join(homedir(), ".arkaos", "keys.json");

const PROVIDERS = {
  OPENAI_API_KEY: { name: "OpenAI", used_for: "Whisper transcription, embeddings, GPT" },
  OPENROUTER_API_KEY: { name: "OpenRouter", used_for: "Model Fabric: one key, hundreds of models (Kimi, DeepSeek, GPT, Gemini) for roles + fusion" },
  GOOGLE_API_KEY: { name: "Google", used_for: "Gemini API, Nano Banana, Google Cloud AI" },
  FAL_API_KEY: { name: "fal.ai", used_for: "Image generation, video generation" },
  MAGIC_API_KEY: { name: "21st.dev Magic", used_for: "Frontend UI/UX component generation (Magic MCP)" },
  GRAPHIFY_TOKEN: { name: "Graphify", used_for: "Knowledge-graph MCP (query_graph, god_nodes) — Bearer token for the graphify HTTP endpoint" },
};

function loadKeys() {
  if (!existsSync(KEYS_PATH)) return {};
  return JSON.parse(readFileSync(KEYS_PATH, "utf-8"));
}

// Temp + rename over the file holding EVERY provider key. Writing in place
// meant a crash mid-write left truncated JSON — and loadKeys() would then
// throw, or a tolerant reader would see {}, silently discarding the lot.
// `wx` refuses a pre-existing temp so a planted symlink cannot capture the
// keys; `mode` applies on create, which is why in-place chmod left a window.
function saveKeys(keys) {
  const tmp = `${KEYS_PATH}.tmp-${process.pid}`;
  try {
    writeFileSync(tmp, JSON.stringify(keys, null, 2), { mode: 0o600, flag: "wx" });
    try { chmodSync(tmp, 0o600); } catch { /* best effort */ }
    renameSync(tmp, KEYS_PATH);
  } catch (err) {
    try { if (existsSync(tmp)) unlinkSync(tmp); } catch { /* best effort */ }
    throw err;
  }
}

function mask(value) {
  if (!value) return "";
  return value.length > 10 ? value.slice(0, 4) + "..." + value.slice(-4) : "****";
}

export async function keys(args) {
  const [action, keyName, keyValue] = args;

  if (action === "set") {
    if (!keyName || !keyValue) {
      console.error("  Usage: npx arkaos keys set KEY_NAME value");
      console.error("\n  Available keys:");
      for (const [k, v] of Object.entries(PROVIDERS)) {
        console.error(`    ${k.padEnd(20)} ${v.name} — ${v.used_for}`);
      }
      process.exit(1);
    }
    const keys = loadKeys();
    keys[keyName] = keyValue;
    saveKeys(keys);
    console.log(`\n  Set ${keyName} = ${mask(keyValue)}`);
    console.log(`  Stored in: ${KEYS_PATH}\n`);
    return;
  }

  if (action === "remove" || action === "delete") {
    if (!keyName) {
      console.error("  Usage: npx arkaos keys remove KEY_NAME");
      process.exit(1);
    }
    const keys = loadKeys();
    if (keyName in keys) {
      delete keys[keyName];
      saveKeys(keys);
      console.log(`\n  Removed ${keyName}\n`);
    } else {
      console.log(`\n  Key ${keyName} not found.\n`);
    }
    return;
  }

  // Default: list keys
  const keys = loadKeys();
  console.log("\n  ArkaOS API Keys\n");

  for (const [k, v] of Object.entries(PROVIDERS)) {
    const value = keys[k] || process.env[k] || "";
    const status = value ? "\x1b[32m configured\x1b[0m" : "\x1b[90m not set\x1b[0m";
    const masked = keys[k] ? mask(keys[k]) : (process.env[k] ? "(env)" : "");
    console.log(`  ${k.padEnd(22)} ${v.name.padEnd(12)} ${status}  ${masked}`);
  }

  // Custom keys
  for (const [k, v] of Object.entries(keys)) {
    if (!(k in PROVIDERS)) {
      console.log(`  ${k.padEnd(22)} Custom       \x1b[32m configured\x1b[0m  ${mask(v)}`);
    }
  }

  console.log(`\n  Set a key:    npx arkaos keys set OPENAI_API_KEY sk-...`);
  console.log(`  Remove a key: npx arkaos keys remove OPENAI_API_KEY\n`);
}
