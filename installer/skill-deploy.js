import {
  copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, readFileSync,
  statSync, writeFileSync,
} from "node:fs";
import { join } from "node:path";

import { resolveFile } from "./path-resolver.js";

// Single skill-deployment implementation shared by the fresh-install
// path (index.js::installSkill) and the update path (update.js §6) —
// the same single-source pattern as hook-lib.js::copyHookLib, and for
// the same reason: the two loops HAD drifted. update.js §6 deployed
// hubs + sub-skills + agents but never the 14 meta skills
// (arka/skills/* — including arka-flow, the evidence-flow
// NON-NEGOTIABLE) nor the nested reference bundle, so any update-only
// machine was silently missing them (F2-7c-pre).
//
// Markdown semantics: safeResolveMarkdown everywhere — resolveFile
// substitutes ${VAR} path tokens and falls back to a raw copy when
// resolution fails. This is the update.js behavior; index.js used to
// raw-copy, so unifying on the resolving superset fixes install too.

function listSubdirs(parent) {
  if (!existsSync(parent)) return [];
  try {
    return readdirSync(parent, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
  } catch {
    return [];
  }
}

function safeResolveMarkdown(src, dst) {
  try {
    resolveFile(src, dst);
  } catch {
    copyFileSync(src, dst);
  }
}

export function copySkillResources(skillSrcDir, skillDestDir) {
  for (const res of ["scripts", "references", "assets"]) {
    const src = join(skillSrcDir, res);
    if (!existsSync(src)) continue;
    try {
      cpSync(src, join(skillDestDir, res), { recursive: true });
    } catch {
      // Best-effort — a missing resource dir must not break deploy.
    }
  }
}

function deployTopLevelSkill(skillSrcDir, arkaName, skillsBase) {
  const skillMd = join(skillSrcDir, "SKILL.md");
  if (!existsSync(skillMd)) return false;
  const dest = join(skillsBase, arkaName);
  mkdirSync(dest, { recursive: true });
  safeResolveMarkdown(skillMd, join(dest, "SKILL.md"));
  copySkillResources(skillSrcDir, dest);
  return true;
}

/**
 * Deploy the full skill surface: main /arka skill (+ nested reference
 * bundle), department hubs, sub-skills, meta skills and agent personas.
 * Copy-only — never deletes anything already deployed.
 *
 * Returns per-category counts so both callers can keep their own log
 * style. `version`/`repoRoot` stamp the main skill's VERSION and
 * .repo-path exactly as both callers did before.
 */
export function deploySkills({
  repoRoot,
  skillsBase,
  agentsBase = null,
  version = "",
  mode = "full",
  log = () => {},
}) {
  const counts = { main: 0, bundle: 0, depts: 0, subs: 0, meta: 0, agents: 0 };
  // Curated mode (F2-7c): sub-skills outside the curated cut stay in
  // the repo and ship via the marketplace plugins instead. The curated
  // classification comes from the GENERATED knowledge/skills-manifest
  // (drift-locked to config/skills-curated.yaml). Manifest unreadable
  // -> deploy everything (fail-open: never silently shrink an install
  // because a file was missing).
  const curatedFilter = mode === "curated"
    ? loadCuratedFilter(repoRoot)
    : null;

  // ── Main /arka skill + nested reference bundle ──────────────────────
  const skillSrc = join(repoRoot, "arka", "SKILL.md");
  const skillDest = join(skillsBase, "arka");
  mkdirSync(skillDest, { recursive: true });
  if (existsSync(skillSrc)) {
    safeResolveMarkdown(skillSrc, join(skillDest, "SKILL.md"));
    writeFileSync(join(skillDest, ".repo-path"), repoRoot);
    if (version) writeFileSync(join(skillDest, "VERSION"), version);
    counts.main = 1;
    const nestedSrc = join(repoRoot, "arka", "skills");
    if (existsSync(nestedSrc)) {
      try {
        cpSync(nestedSrc, join(skillDest, "skills"), { recursive: true });
        counts.bundle = 1;
      } catch {
        // Bundled references only — never fail the deploy over them.
      }
    }
  }

  // ── Department hubs + sub-skills ────────────────────────────────────
  const deptRoot = join(repoRoot, "departments");
  for (const dept of listSubdirs(deptRoot)) {
    if (deployTopLevelSkill(join(deptRoot, dept), `arka-${dept}`, skillsBase)) {
      counts.depts++;
    }
    const deptSkillsDir = join(deptRoot, dept, "skills");
    for (const sub of listSubdirs(deptSkillsDir)) {
      if (curatedFilter && !curatedFilter.has(sub)) continue;
      if (deployTopLevelSkill(
        join(deptSkillsDir, sub), `arka-${sub}`, skillsBase)) {
        counts.subs++;
      }
    }
  }

  // ── Meta skills (arka/skills/* as invocable top-level arka-<skill>) ─
  const metaRoot = join(repoRoot, "arka", "skills");
  for (const meta of listSubdirs(metaRoot)) {
    if (deployTopLevelSkill(join(metaRoot, meta), `arka-${meta}`, skillsBase)) {
      counts.meta++;
    }
  }

  // ── Agent personas ──────────────────────────────────────────────────
  if (agentsBase) {
    counts.agents = deployAgents(deptRoot, agentsBase);
  }

  log(counts);
  return counts;
}

function loadCuratedFilter(repoRoot) {
  try {
    const manifest = JSON.parse(readFileSync(
      join(repoRoot, "knowledge", "skills-manifest.json"), "utf-8"));
    const curated = new Set();
    for (const [slug, entry] of Object.entries(manifest.skills || {})) {
      if (entry.curated) curated.add(slug);
    }
    return curated.size > 0 ? curated : null;
  } catch {
    return null; // fail-open: full deploy beats a silently empty one
  }
}

function deployAgents(deptRoot, agentsBase) {
  mkdirSync(agentsBase, { recursive: true });
  let deployed = 0;
  for (const dept of listSubdirs(deptRoot)) {
    const agentsSrc = join(deptRoot, dept, "agents");
    if (!existsSync(agentsSrc)) continue;
    try {
      deployed += deployDeptAgents(agentsSrc, agentsBase);
    } catch {
      // Unreadable agents dir — skip the department, not the deploy.
    }
  }
  return deployed;
}

function deployDeptAgents(agentsSrc, agentsBase) {
  let deployed = 0;
  for (const file of readdirSync(agentsSrc)) {
    if (!file.endsWith(".md")) continue;
    const srcFile = join(agentsSrc, file);
    try {
      if (!statSync(srcFile).isFile()) continue;
    } catch {
      continue;
    }
    copyFileSync(
      srcFile, join(agentsBase, `arka-${file.replace(/\.md$/, "")}.md`));
    deployed++;
  }
  return deployed;
}
