import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { deployCoreSnapshot } from "../../installer/core-snapshot.js";

function makeArkaosRoot({
  withSync = true,
  withVersion = true,
  withRootDirs = true,
} = {}) {
  const root = mkdtempSync(join(tmpdir(), "arka-snap-src-"));
  const core = join(root, "core");
  mkdirSync(join(core, "hooks"), { recursive: true });
  writeFileSync(join(core, "__init__.py"), "");
  writeFileSync(join(core, "hooks", "__init__.py"), "");
  writeFileSync(join(core, "hooks", "_shared.py"), "# shared\n");
  if (withSync) {
    mkdirSync(join(core, "sync"), { recursive: true });
    writeFileSync(join(core, "sync", "__init__.py"), "");
    writeFileSync(join(core, "sync", "engine.py"), "# engine\n");
  }
  const pycache = join(core, "hooks", "__pycache__");
  mkdirSync(pycache, { recursive: true });
  writeFileSync(join(pycache, "_shared.cpython-312.pyc"), "bytecode");
  if (withRootDirs) {
    mkdirSync(join(root, "config"), { recursive: true });
    writeFileSync(join(root, "config", "user-claude.md"), "# base claude.md\n");
    writeFileSync(join(root, "config", "constitution.yaml"), "rules: []\n");
    mkdirSync(join(root, "departments", "dev", "agents"), { recursive: true });
    writeFileSync(
      join(root, "departments", "dev", "agents", "backend-dev.yaml"),
      "id: backend-dev\n",
    );
    mkdirSync(join(root, "knowledge"), { recursive: true });
    writeFileSync(join(root, "knowledge", "agents-registry-v2.json"), "{}\n");
  }
  if (withVersion) writeFileSync(join(root, "VERSION"), "9.9.9\n");
  return root;
}

test("deployCoreSnapshot copies core + VERSION and skips __pycache__", () => {
  const src = makeArkaosRoot();
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    assert.equal(deployCoreSnapshot(src, installDir), true);
    const lib = join(installDir, "lib");
    assert.ok(existsSync(join(lib, "core", "sync", "__init__.py")), "sync marker not deployed");
    assert.equal(readFileSync(join(lib, "core", "hooks", "_shared.py"), "utf-8"), "# shared\n");
    assert.equal(readFileSync(join(lib, "VERSION"), "utf-8"), "9.9.9\n");
    assert.ok(!existsSync(join(lib, "core", "hooks", "__pycache__")), "__pycache__ leaked into snapshot");
    assert.ok(!existsSync(join(lib, ".core.staging")), "staging dir left behind");
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});

test("deployCoreSnapshot copies every root-relative dir the core reads", () => {
  const src = makeArkaosRoot();
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    assert.equal(deployCoreSnapshot(src, installDir), true);
    const lib = join(installDir, "lib");
    assert.equal(
      readFileSync(join(lib, "config", "user-claude.md"), "utf-8"),
      "# base claude.md\n",
      "config/ missing — content sync phase breaks on a purged npx cache",
    );
    assert.ok(
      existsSync(join(lib, "departments", "dev", "agents", "backend-dev.yaml")),
      "departments/ missing — agent provisioning phase breaks on a purged npx cache",
    );
    assert.ok(
      existsSync(join(lib, "knowledge", "agents-registry-v2.json")),
      "knowledge/ missing — registry readers break on a purged npx cache",
    );
    for (const dir of ["config", "departments", "knowledge"]) {
      assert.ok(!existsSync(join(lib, `.${dir}.staging`)), `${dir} staging dir left behind`);
      assert.ok(!existsSync(join(lib, `.${dir}.previous`)), `${dir} previous dir left behind`);
    }
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});

test("deployCoreSnapshot refuses a source without the full core package", () => {
  const src = makeArkaosRoot({ withSync: false });
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    assert.equal(deployCoreSnapshot(src, installDir), false);
    assert.ok(!existsSync(join(installDir, "lib", "core")), "partial core must not be snapshotted");
    assert.ok(!existsSync(join(installDir, "lib", "config")), "partial root must not be snapshotted");
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});

test("deployCoreSnapshot replaces a stale snapshot on re-deploy", () => {
  const src = makeArkaosRoot();
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    const staleDir = join(installDir, "lib", "core", "sync");
    mkdirSync(staleDir, { recursive: true });
    writeFileSync(join(staleDir, "removed_module.py"), "# stale\n");
    const staleConfig = join(installDir, "lib", "config");
    mkdirSync(staleConfig, { recursive: true });
    writeFileSync(join(staleConfig, "removed-standard.md"), "# stale\n");
    assert.equal(deployCoreSnapshot(src, installDir), true);
    assert.ok(
      !existsSync(join(staleDir, "removed_module.py")),
      "stale core files must not survive a re-deploy",
    );
    assert.ok(
      !existsSync(join(staleConfig, "removed-standard.md")),
      "stale config files must not survive a re-deploy",
    );
    assert.ok(existsSync(join(staleDir, "engine.py")), "fresh files missing after re-deploy");
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});

test("deployCoreSnapshot keeps an existing snapshot dir when the source lacks it", () => {
  const src = makeArkaosRoot({ withRootDirs: false });
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    const existingConfig = join(installDir, "lib", "config");
    mkdirSync(existingConfig, { recursive: true });
    writeFileSync(join(existingConfig, "user-claude.md"), "# kept\n");
    assert.equal(deployCoreSnapshot(src, installDir), true);
    assert.equal(
      readFileSync(join(existingConfig, "user-claude.md"), "utf-8"),
      "# kept\n",
      "a source missing an optional dir must not delete the existing snapshot copy",
    );
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});

test("deployCoreSnapshot cleans orphaned staging/previous dirs from a crashed run", () => {
  const src = makeArkaosRoot();
  const installDir = mkdtempSync(join(tmpdir(), "arka-snap-dest-"));
  try {
    const lib = join(installDir, "lib");
    mkdirSync(join(lib, ".core.staging", "core"), { recursive: true });
    writeFileSync(join(lib, ".core.staging", "core", "half-written.py"), "# crash leftover\n");
    mkdirSync(join(lib, ".core.previous", "core"), { recursive: true });
    writeFileSync(join(lib, ".core.previous", "core", "old.py"), "# crash leftover\n");
    mkdirSync(join(lib, ".config.staging"), { recursive: true });
    writeFileSync(join(lib, ".config.staging", "half.md"), "# crash leftover\n");
    assert.equal(deployCoreSnapshot(src, installDir), true);
    assert.ok(!existsSync(join(lib, ".core.staging")), "orphaned staging dir not cleaned");
    assert.ok(!existsSync(join(lib, ".core.previous")), "orphaned previous dir not cleaned");
    assert.ok(!existsSync(join(lib, ".config.staging")), "orphaned config staging dir not cleaned");
    assert.ok(existsSync(join(lib, "core", "sync", "__init__.py")), "snapshot not deployed");
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(installDir, { recursive: true, force: true });
  }
});
