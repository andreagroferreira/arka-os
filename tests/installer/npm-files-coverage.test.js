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

test("no installer source dir is excluded by .npmignore (second silent-skip vector)", () => {
  // QG redo 1: mcps/ sat in BOTH package.json files and .npmignore
  // ("Legacy v1" — a false label). It only shipped because npm's files
  // allowlist wins precedence — version-sensitive behavior, not a
  // documented guarantee. Contradictory distribution config must fail
  // the build, not ride on precedence.
  const ignoreRules = readFileSync(join(ROOT, ".npmignore"), "utf-8")
    .split("\n")
    .map((l) => l.trim().replace(/\/$/, ""))
    .filter((l) => l && !l.startsWith("#"));
  const excluded = [...installerSourceDirs()].filter(
    (d) => ignoreRules.includes(d)
  );
  assert.deepEqual(excluded, [],
    `.npmignore excludes installer source dirs — contradicts package.json ` +
    `files and re-arms the silent skip if precedence ever changes: ${excluded}`);
});

test("the tarball ships no bytecode or OS cruft (executable lock, not a config mirror)", async () => {
  // QG follow-up (F2-7b review): 462 __pycache__/*.pyc files rode the
  // v4.14.0 tarball because .npmignore is largely inert for content
  // inside files-included dirs. The negation patterns in "files" fix
  // it; this lock runs the REAL packer so the claim stays executable.
  const { execFileSync } = await import("node:child_process");
  const out = execFileSync(
    "npm", ["pack", "--dry-run", "--json"],
    { cwd: ROOT, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }
  );
  const [report] = JSON.parse(out);
  const cruft = report.files
    .map((f) => f.path)
    .filter((p) => /\.pyc$|__pycache__|\.DS_Store$/.test(p));
  assert.deepEqual(cruft.slice(0, 5), [],
    `${cruft.length} cruft file(s) in the npm tarball`);
});
