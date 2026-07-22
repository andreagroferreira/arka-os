/**
 * Product stats — derived at runtime, never hand-typed (Foundation PR-3
 * QG minor; docs-as-code rule: counts come from the shipped artifacts).
 *
 * Sources (all ship in the npm tarball — see package.json "files"):
 *   agents       knowledge/agents-registry-v2.json  → agents[].length
 *   departments  departments/                        → directory count
 *   skills       knowledge/skills-manifest.json      → skills map +
 *                structural surface (main + hubs + meta) — the full
 *                deployable skill surface installer/skill-deploy.js ships
 *
 * Contract: any missing/corrupt source yields null for THAT field only.
 * Callers must omit the corresponding output line — an invented number
 * is worse than no number.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

export function readProductStats(repoRoot) {
  return {
    agents: countAgents(repoRoot),
    departments: countDepartments(repoRoot),
    skills: countSkills(repoRoot),
  };
}

/**
 * Render the summary lines for the install report. Null fields are
 * omitted; when the department count is unavailable the agents line
 * degrades to the bare count instead of inventing a denominator.
 */
export function productStatsLines(stats) {
  const lines = [];
  if (stats.agents !== null) {
    lines.push(
      stats.departments !== null
        ? `Agents:      ${stats.agents} across ${stats.departments} departments`
        : `Agents:      ${stats.agents}`,
    );
  }
  if (stats.skills !== null) {
    lines.push(`Skills:      ${stats.skills} backed by enterprise frameworks`);
  }
  return lines;
}

function countAgents(repoRoot) {
  try {
    const registry = JSON.parse(
      readFileSync(join(repoRoot, "knowledge", "agents-registry-v2.json"), "utf-8"),
    );
    if (Array.isArray(registry.agents)) return registry.agents.length;
    return null;
  } catch {
    return null;
  }
}

function countDepartments(repoRoot) {
  try {
    const base = join(repoRoot, "departments");
    if (!existsSync(base)) return null;
    const count = readdirSync(base, { withFileTypes: true }).filter((e) =>
      e.isDirectory(),
    ).length;
    return count > 0 ? count : null;
  } catch {
    return null;
  }
}

function countSkills(repoRoot) {
  try {
    const manifest = JSON.parse(
      readFileSync(join(repoRoot, "knowledge", "skills-manifest.json"), "utf-8"),
    );
    const skills = manifest.skills;
    if (!skills || typeof skills !== "object" || Array.isArray(skills)) {
      return null;
    }
    let count = Object.keys(skills).length;
    const structural = manifest.structural;
    if (structural && typeof structural === "object") {
      if (structural.main) count += 1;
      if (Array.isArray(structural.hubs)) count += structural.hubs.length;
      if (Array.isArray(structural.meta)) count += structural.meta.length;
    }
    return count;
  } catch {
    return null;
  }
}
