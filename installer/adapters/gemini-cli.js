import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { readBundleFile } from "../harness-bundle.js";

export default {
  configureHooks(config, installDir) {
    // Gemini CLI reads GEMINI.md. Deploy the generated ArkaOS bundle
    // (scripts/harness_gen.py) instead of the old pointer to a
    // config/gemini-instructions.md that never existed.
    const bundle = readBundleFile("gemini", "GEMINI.md");
    if (!bundle) {
      console.warn(
        "         Gemini bundle missing (harness/gemini/GEMINI.md) — " +
          "run scripts/harness_gen.py; skipping GEMINI.md."
      );
      return;
    }
    mkdirSync(config.configDir, { recursive: true });
    writeFileSync(join(config.configDir, "GEMINI.md"), bundle);
    console.log("         Gemini CLI GEMINI.md configured (ArkaOS bundle).");
  },
};
