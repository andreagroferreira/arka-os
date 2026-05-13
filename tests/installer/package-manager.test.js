import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildInstallCommand,
  formatSudoInstructions,
  managerNeedsSudo,
} from "../../installer/package-manager.js";

test("brew install uses --cask for cask: prefix", () => {
  assert.equal(
    buildInstallCommand("brew", "cask:obsidian"),
    "brew install --cask obsidian"
  );
});

test("brew install uses plain form for non-cask packages", () => {
  assert.equal(buildInstallCommand("brew", "node"), "brew install node");
});

test("apt install prepends sudo and runs update first", () => {
  assert.equal(
    buildInstallCommand("apt", "nodejs"),
    "sudo apt update && sudo apt install -y nodejs"
  );
});

test("snap install adds --classic for :classic suffix", () => {
  assert.equal(
    buildInstallCommand("snap", "obsidian:classic"),
    "sudo snap install obsidian --classic"
  );
});

test("snap install is plain for non-classic packages", () => {
  assert.equal(buildInstallCommand("snap", "code"), "sudo snap install code");
});

test("winget install accepts source + package agreements silently", () => {
  assert.equal(
    buildInstallCommand("winget", "Obsidian.Obsidian"),
    "winget install --id Obsidian.Obsidian --silent --accept-source-agreements --accept-package-agreements"
  );
});

test("choco install passes -y for unattended", () => {
  assert.equal(buildInstallCommand("choco", "nodejs"), "choco install nodejs -y");
});

test("unknown manager returns empty string", () => {
  assert.equal(buildInstallCommand("yum", "anything"), "");
});

test("managerNeedsSudo only true for apt and snap", () => {
  assert.equal(managerNeedsSudo("apt"), true);
  assert.equal(managerNeedsSudo("snap"), true);
  assert.equal(managerNeedsSudo("brew"), false);
  assert.equal(managerNeedsSudo("winget"), false);
  assert.equal(managerNeedsSudo("choco"), false);
  assert.equal(managerNeedsSudo(null), false);
});

test("formatSudoInstructions returns empty for empty input", () => {
  assert.equal(formatSudoInstructions([]), "");
  assert.equal(formatSudoInstructions(null), "");
});

test("formatSudoInstructions deduplicates and wraps copy-paste block", () => {
  const out = formatSudoInstructions([
    "sudo apt install -y nodejs",
    "sudo apt install -y nodejs",
    "sudo snap install obsidian --classic",
  ]);
  assert.match(out, /To finish setup/);
  assert.match(out, /sudo apt install -y nodejs/);
  assert.match(out, /sudo snap install obsidian --classic/);
  assert.match(out, /Then re-run: npx arkaos install/);
  // Deduplicated — only one apt line
  const aptCount = (out.match(/sudo apt install -y nodejs/g) || []).length;
  assert.equal(aptCount, 1);
});

test("formatSudoInstructions strips falsy entries", () => {
  const out = formatSudoInstructions(["", null, "sudo apt install -y nodejs", undefined]);
  assert.match(out, /sudo apt install -y nodejs/);
});
