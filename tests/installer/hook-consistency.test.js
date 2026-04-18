import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function extractStringArray(source, varName) {
  const re = new RegExp(
    `(?:const|let|var)\\s+${varName}\\s*=\\s*\\[([\\s\\S]*?)\\]`,
    "m"
  );
  const m = source.match(re);
  if (!m) throw new Error(`Could not locate array ${varName}`);
  return [...m[1].matchAll(/["']([^"']+)["']/g)].map((x) => x[1]);
}

function extractRegisteredHooks(adapterSource) {
  const names = [];
  for (const m of adapterSource.matchAll(
    /hookEntry\s*\(\s*hooksDir\s*,\s*["']([^"']+)["']/g
  )) {
    names.push(m[1]);
  }
  return names;
}

const adapterSrc = readFileSync(
  join(ROOT, "installer/adapters/claude-code.js"),
  "utf-8"
);
const installerSrc = readFileSync(
  join(ROOT, "installer/index.js"),
  "utf-8"
);
const doctorSrc = readFileSync(
  join(ROOT, "installer/doctor.js"),
  "utf-8"
);

const registered = extractRegisteredHooks(adapterSrc);
const copied = extractStringArray(installerSrc, "hookNames");
const doctorRequired = extractStringArray(doctorSrc, "required");

test("adapter registers at least one hook", () => {
  assert.ok(registered.length > 0, "no hooks found in adapter");
});

test("every hook registered by the adapter is copied by the installer", () => {
  const missing = registered.filter((h) => !copied.includes(h));
  assert.deepEqual(
    missing,
    [],
    `installer/index.js hookNames is missing: ${missing.join(", ")} — add them to the hookNames array or the hook will never reach ~/.arkaos/config/hooks/ (see v2.20.0 regression)`
  );
});

test("every hook copied by the installer is validated by the doctor", () => {
  const missing = copied.filter((h) => !doctorRequired.includes(h));
  assert.deepEqual(
    missing,
    [],
    `installer/doctor.js "required" list is missing: ${missing.join(", ")} — drift between installer and doctor will hide future breakage`
  );
});

test("every hook copied has a source .sh file in config/hooks/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const missing = copied.filter(
    (h) => !existsSync(join(hooksDir, `${h}.sh`))
  );
  assert.deepEqual(
    missing,
    [],
    `config/hooks/ is missing .sh files for: ${missing.join(", ")}`
  );
});

test("every hook copied has a source .ps1 file in config/hooks/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const missing = copied.filter(
    (h) => !existsSync(join(hooksDir, `${h}.ps1`))
  );
  assert.deepEqual(
    missing,
    [],
    `config/hooks/ is missing .ps1 files for: ${missing.join(", ")}`
  );
});

test("_lib/ deps referenced by hooks exist in config/hooks/_lib/", () => {
  const hooksDir = join(ROOT, "config/hooks");
  const libDir = join(hooksDir, "_lib");
  const referenced = new Set();
  for (const h of copied) {
    const sh = join(hooksDir, `${h}.sh`);
    if (!existsSync(sh)) continue;
    const src = readFileSync(sh, "utf-8");
    for (const m of src.matchAll(/_lib\/([a-zA-Z0-9_-]+\.sh)/g)) {
      referenced.add(m[1]);
    }
  }
  const present = existsSync(libDir)
    ? new Set(readdirSync(libDir).filter((f) => f.endsWith(".sh")))
    : new Set();
  const missing = [...referenced].filter((f) => !present.has(f));
  assert.deepEqual(
    missing,
    [],
    `config/hooks/_lib/ is missing files referenced by hooks: ${missing.join(", ")}`
  );
});

test("VERSION file matches package.json version", () => {
  const pkg = JSON.parse(
    readFileSync(join(ROOT, "package.json"), "utf-8")
  );
  const versionFile = readFileSync(join(ROOT, "VERSION"), "utf-8").trim();
  assert.equal(
    pkg.version,
    versionFile,
    "VERSION and package.json version must match before publish"
  );
});
