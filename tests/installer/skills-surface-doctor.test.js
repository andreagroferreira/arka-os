// F2-7c non-gating follow-ups, folded here (QG record): the doctor's
// skills-surface check and the cli --skills threading had no locks.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { checks } from "../../installer/doctor.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const byName = Object.fromEntries(checks.map((c) => [c.name, c]));

test("skills-surface doctor check is registered, warn-only and delete-free", () => {
  const check = byName["skills-surface"];
  assert.ok(check, "skills-surface check missing from the doctor");
  assert.equal(check.severity, "warn",
    "the doctor may flag leftovers, never fail an install over them");
  const src = check.check.toString();
  assert.ok(!/rmSync|unlink|rmdir/.test(src),
    "the doctor classifies, it NEVER deletes skills");
});

test("cli threads --skills through to update() (strict:false lesson)", () => {
  const cliSrc = readFileSync(join(ROOT, "installer", "cli.js"), "utf-8");
  assert.match(cliSrc, /skills:\s*\{\s*type:\s*"string"\s*\}/,
    "--skills must be DECLARED in parseArgs options");
  assert.match(cliSrc, /update\(\{\s*skillsFlag:\s*values\.skills/,
    "cli must pass values.skills to update()");
});
