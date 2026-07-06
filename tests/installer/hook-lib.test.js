import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync, statSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { copyHookLib } from "../../installer/hook-lib.js";

function makeSrcHooksDir(withLib) {
  const dir = mkdtempSync(join(tmpdir(), "arka-hook-lib-"));
  if (withLib) {
    const lib = join(dir, "_lib");
    mkdirSync(lib);
    writeFileSync(join(lib, "arka_python.sh"), "#!/usr/bin/env bash\n");
    writeFileSync(join(lib, "arka_python.ps1"), "# ps resolver\n");
  }
  return dir;
}

test("copyHookLib deploys _lib recursively and chmods .sh files", () => {
  const src = makeSrcHooksDir(true);
  const dest = mkdtempSync(join(tmpdir(), "arka-hook-dest-"));
  try {
    assert.equal(copyHookLib(src, dest), true);
    const sh = join(dest, "_lib", "arka_python.sh");
    const ps1 = join(dest, "_lib", "arka_python.ps1");
    assert.ok(existsSync(sh), "arka_python.sh not deployed");
    assert.ok(existsSync(ps1), "arka_python.ps1 not deployed");
    assert.equal(readFileSync(sh, "utf-8"), "#!/usr/bin/env bash\n");
    if (process.platform !== "win32") {
      assert.ok(statSync(sh).mode & 0o100, "arka_python.sh must be executable");
    }
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(dest, { recursive: true, force: true });
  }
});

test("copyHookLib returns false when source has no _lib/", () => {
  const src = makeSrcHooksDir(false);
  const dest = mkdtempSync(join(tmpdir(), "arka-hook-dest-"));
  try {
    assert.equal(copyHookLib(src, dest), false);
    assert.ok(!existsSync(join(dest, "_lib")), "must not create dest _lib");
  } finally {
    rmSync(src, { recursive: true, force: true });
    rmSync(dest, { recursive: true, force: true });
  }
});

test("update.js and index.js both route _lib deploy through copyHookLib", () => {
  for (const flow of ["update.js", "index.js"]) {
    const body = readFileSync(join(process.cwd(), "installer", flow), "utf-8");
    assert.match(body, /\bcopyHookLib\(/, `installer/${flow} must call copyHookLib()`);
    assert.doesNotMatch(
      body,
      /cpSync\(\s*srcLibDir/,
      `installer/${flow} must not keep its own _lib copy loop`
    );
  }
});
