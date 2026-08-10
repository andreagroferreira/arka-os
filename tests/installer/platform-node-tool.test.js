// Tests for nodeToolCommand() — the cross-platform argv builder for
// npm/npx/pnpm invocations from the installer.
//
// The regression these guard is Windows-only but the assertions run
// everywhere: `spawnSync("npm", ...)` fails with ENOENT on Windows because
// npm ships as `npm.cmd`, and `spawnSync("npm.cmd", ...)` fails with EINVAL
// because Node refuses to launch batch files without a shell. Both silently
// degraded `installMotionKit` and `installImpeccableDetector` to "failed" on
// every Windows install.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { platform } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const { nodeToolCommand, IS_WINDOWS } = await import(
  pathToFileURL(join(ROOT, "installer", "platform.js"))
);

test("nodeToolCommand passes the tool through unchanged on POSIX", { skip: IS_WINDOWS }, () => {
  const [cmd, argv] = nodeToolCommand("npm", ["install", "-g", "pkg@^1.0"]);
  assert.equal(cmd, "npm");
  assert.deepEqual(argv, ["install", "-g", "pkg@^1.0"]);
});

test("nodeToolCommand routes through cmd.exe on Windows", { skip: !IS_WINDOWS }, () => {
  // The caret arrives doubled ON PURPOSE: cmd.exe consumes one before the
  // program parses the line. The previous form of this assertion expected
  // `pkg@^1.0` here and therefore locked in the bug.
  const [cmd, argv] = nodeToolCommand("npm", ["install", "-g", "pkg@^1.0"]);
  assert.equal(cmd, "cmd.exe");
  assert.deepEqual(argv, ["/c", "npm", "install", "-g", "pkg@^^1.0"]);
});

test("a whitespace-bearing argument keeps its caret undoubled", { skip: !IS_WINDOWS }, () => {
  // Node quotes this one, and inside quotes cmd.exe leaves `^` alone.
  // Doubling here would deliver a literal `^^` — measured, which is why the
  // escape is conditional rather than blanket.
  const [, argv] = nodeToolCommand("npm", ["install", "pkg@^1.0 extra"]);
  assert.deepEqual(argv, ["/c", "npm", "install", "pkg@^1.0 extra"]);
});

test("nodeToolCommand keeps arguments as discrete argv entries", () => {
  // Never a pre-joined string: `shell: true` would concatenate these and
  // reintroduce DEP0190's escaping hazard for versions like `pkg@^1.0`.
  const [, argv] = nodeToolCommand("npx", ["-y", "some pkg"]);
  assert.ok(Array.isArray(argv));
  assert.ok(argv.includes("some pkg"));
});

test("nodeToolCommand defaults to an empty argument list", () => {
  const [, argv] = nodeToolCommand("npm");
  assert.deepEqual(argv, IS_WINDOWS ? ["/c", "npm"] : []);
});

// The detector-proving test: this is the one that fails without the fix.
// It spawns the REAL npm the same way the installer does. On Windows the
// pre-fix form (`spawnSync("npm", ...)`) errors with ENOENT, so a passing
// run here is evidence the argv builder produces something launchable on
// the host platform — not merely a plausible-looking array.
// The detector-proving test for the caret. It runs on EVERY platform and
// asserts the same thing on each: whatever the caller passed is what the
// program receives. On POSIX that has always held (no shell in the path);
// on Windows it fails without the escape, because `impeccable@^3.2` reaches
// npm as `impeccable@3.2` and quietly narrows `>=3.2 <4` to `3.2.x`.
//
// The oracle deliberately contains no spaces (`console.log(process.argv[1])`)
// so the measurement cannot be confounded by Node's own quoting of the -e
// expression. An earlier version of this probe used an interpreter path with
// a space in it and blamed the argument for a failure that belonged to the
// executable.
test("an argument with a caret reaches the program unchanged", () => {
  const SPEC = "impeccable@^3.2";
  const [cmd, argv] = nodeToolCommand("node", [
    "-e", "console.log(process.argv[1])", SPEC,
  ]);
  const out = spawnSync(cmd, argv, {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  assert.equal(out.error, undefined, `spawn failed on ${platform()}: ${out.error?.code}`);
  assert.equal(out.status, 0, String(out.stderr));
  assert.equal(String(out.stdout).trim(), SPEC);
});

test("nodeToolCommand produces an argv that spawnSync can actually launch", () => {
  const [cmd, argv] = nodeToolCommand("npm", ["--version"]);
  const out = spawnSync(cmd, argv, {
    timeout: 60_000,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  assert.equal(out.error, undefined, `spawn failed on ${platform()}: ${out.error?.code}`);
  assert.equal(out.status, 0);
  assert.match(String(out.stdout).trim(), /^\d+\.\d+\.\d+/);
});
