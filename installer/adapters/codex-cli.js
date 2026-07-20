import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { readBundleFile } from "../harness-bundle.js";

export default {
  configureHooks(config, installDir) {
    // Codex CLI reads AGENTS.md. Deploy the generated ArkaOS bundle
    // (scripts/harness_gen.py) — full routing table, agent index, and
    // stack conventions — instead of the old pointer to a
    // config/codex-instructions.md that never existed.
    const bundle = readBundleFile("codex", "AGENTS.md");
    if (!bundle) {
      console.warn(
        "         Codex bundle missing (harness/codex/AGENTS.md) — " +
          "run scripts/harness_gen.py; skipping AGENTS.md."
      );
      return;
    }
    mkdirSync(config.configDir, { recursive: true });
    writeFileSync(join(config.configDir, "AGENTS.md"), bundle);
    console.log("         Codex CLI AGENTS.md configured (ArkaOS bundle).");
  },
};
