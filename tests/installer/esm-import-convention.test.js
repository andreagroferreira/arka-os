// The dynamic-import convention for this suite, pinned.
//
// A dynamic import whose specifier is a raw `join(ROOT, ...)` hands
// Node's ESM loader a bare filesystem path. On POSIX that happens to
// parse; on Windows it is `c:\...` and the loader rejects it outright
// with ERR_UNSUPPORTED_ESM_URL_SCHEME. The file then aborts at LOAD
// time, so none of its assertions run and `node --test` reports a single
// failure where a whole file's worth of coverage should be — which is
// how a real installer defect (#495: a CRLF CLAUDE.md duplicated instead
// of adopted) shipped past the very test file that would have caught it.
//
// `pathToFileURL()` is the fix, and this test is the lock: the #495
// sweep stalled at 13 of 18 call sites precisely because the leftovers
// used the multi-line spelling and a single-line grep could not see
// them. `\s` matches newlines, so both spellings are caught here.
//
// Scope, stated honestly: this catches the path-BUILDER idioms (`join`
// or `resolve` invoked directly inside the import), which is every
// occurrence in this suite. It cannot catch an import of a variable that
// happens to hold a bare path — for that case build the URL at the
// assignment instead (prompts-headless.test.js and ui-fallback.test.js
// pass a `.href` through, and are the precedent to copy).
//
// This file is scanned along with its siblings: no self-exemption, which
// is why the prose above never spells the forbidden call out literally.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const BARE_PATH_IMPORT = /await\s+import\(\s*(?:join|resolve)\(/;

test("every installer test imports through pathToFileURL, never a bare path", () => {
  const offenders = readdirSync(HERE)
    .filter((name) => name.endsWith(".test.js"))
    .filter((name) => BARE_PATH_IMPORT.test(readFileSync(join(HERE, name), "utf-8")));

  assert.deepEqual(
    offenders,
    [],
    `bare-path dynamic import in: ${offenders.join(", ")} — wrap the path in `
    + "pathToFileURL(); on Windows the ESM loader rejects it and the whole "
    + "file aborts at load with zero assertions executed",
  );
});
