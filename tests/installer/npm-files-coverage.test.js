// Distribution lock: every repo directory the installer deploys FROM
// must ship in the npm tarball. The v4.14.0 gap: mcps/ was absent from
// package.json "files", so every deploy block guarded by
// existsSync(join(ARKAOS_ROOT, "mcps")) silently skipped on npm
// installs — the arka-tools MCP server never reached any user machine
// (found live by `arkaos doctor` on the operator's install).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf-8"));

function installerSourceDirs() {
  const dirs = new Set();
  const scan = (dir) => {
    for (const f of readdirSync(dir, { withFileTypes: true })) {
      if (f.isDirectory()) { scan(join(dir, f.name)); continue; }
      if (!f.name.endsWith(".js")) continue;
      const src = readFileSync(join(dir, f.name), "utf-8");
      for (const m of src.matchAll(/join\(ARKAOS_ROOT, "([a-z-]+)"/g)) {
        dirs.add(m[1]);
      }
    }
  };
  scan(join(ROOT, "installer"));
  return dirs;
}

test("every ARKAOS_ROOT dir the installer reads ships in the npm tarball", () => {
  const shipped = new Set(
    pkg.files.map((f) => f.replace(/\/$/, "").split("/")[0])
  );
  const missing = [...installerSourceDirs()].filter((d) => !shipped.has(d));
  assert.deepEqual(missing, [],
    `installer deploys from dirs the npm tarball does not ship — the ` +
    `existsSync guards will skip SILENTLY on user machines: ${missing}`);
});
