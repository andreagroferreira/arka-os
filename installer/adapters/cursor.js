import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { listBundleFiles, readBundleFile } from "../harness-bundle.js";

export default {
  configureHooks(config, installDir) {
    // Cursor reads .cursor/rules/*.mdc — its native strength is
    // path-scoped rules, so the generated bundle ships one always-on
    // contract rule plus a scoped rule per stack. Replaces the old
    // hand-typed rule with fossilized counts and a pointer to a
    // config/cursor-instructions.md that never existed.
    const files = listBundleFiles("cursor", "rules");
    if (files.length === 0) {
      console.warn(
        "         Cursor bundle missing (harness/cursor/rules/) — " +
          "run scripts/harness_gen.py; skipping rules."
      );
      return;
    }
    const rulesDir = join(config.configDir, "rules");
    mkdirSync(rulesDir, { recursive: true });
    for (const name of files) {
      const content = readBundleFile("cursor", join("rules", name));
      if (content) writeFileSync(join(rulesDir, name), content);
    }
    console.log(
      `         Cursor rules configured (${files.length} ArkaOS rules).`
    );
  },
};
