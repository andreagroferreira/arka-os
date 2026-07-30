import {
  copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, readFileSync,
  renameSync, statSync, writeFileSync,
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
 * Copy-and-retire — never deletes anything already deployed (the v1 QG
 * persona retirement renames into .arkaos-legacy/, it does not delete).
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
    const written = new Set();
    counts.agents = deployAgents(deptRoot, agentsBase, written);
    // Gate owners (F2 specialist-gate P0): every owner the ownership
    // rules can demand MUST be dispatchable. 4 of 7 owners existed only
    // as department YAML (never deployed — the agent loop above ships
    // .md only), so the gate told sessions to dispatch agents nobody
    // could invoke. The generated config/agent-roster.json maps each
    // owner to a dispatchable source; hand-authored dept .md files win
    // (already deployed above), compiled ones fill the gaps.
    counts.agents += deployGateOwners(repoRoot, agentsBase, written);
    retireLegacyQgPersonas(agentsBase);
  }

  log(counts);
  return counts;
}

function deployGateOwners(repoRoot, agentsBase, written) {
  let roster;
  try {
    roster = JSON.parse(readFileSync(
      join(repoRoot, "config", "agent-roster.json"), "utf-8"));
  } catch {
    return 0; // older core without the roster — dept loop already ran
  }
  let deployed = 0;
  for (const [slug, entry] of Object.entries(roster.gate_owners || {})) {
    const target = `arka-${slug}.md`;
    if (written.has(target)) continue; // dept .md won this run
    const src = join(repoRoot, entry.source);
    if (!existsSync(src)) continue;
    try {
      copyFileSync(src, join(agentsBase, target));
      written.add(target);
      deployed++;
    } catch {
      // One unreadable agent must not break the deploy.
    }
  }
  return deployed;
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

function deployAgents(deptRoot, agentsBase, written = new Set()) {
  mkdirSync(agentsBase, { recursive: true });
  let deployed = 0;
  for (const dept of listSubdirs(deptRoot)) {
    const agentsSrc = join(deptRoot, dept, "agents");
    if (!existsSync(agentsSrc)) continue;
    try {
      deployed += deployDeptAgents(agentsSrc, agentsBase, written);
    } catch {
      // Unreadable agents dir — skip the department, not the deploy.
    }
  }
  return deployed;
}

// PR-B5 (QG r1 B2): the three v1 Quality Gate personas predate the
// QGVerdict contract. Deployed to ~/.claude/agents/ they keep a
// contract-less cqo / copy-director / tech-ux-director dispatchable at
// USER scope even after every project is repaired — the dead-relay
// shape workstream B closes. The dept loop skips them, and the targets
// this deployer itself wrote in earlier runs are retired — renamed
// into .arkaos-legacy/, never deleted (the copy-only contract holds:
// no delete primitive here). The real reviewers ship per project from
// config/claude-agents/ via deployProjectAgents.
const LEGACY_QG_PERSONA_FILES = [
  "cqo.md", "copy-director.md", "tech-ux-director.md",
];

function retireLegacyQgPersonas(agentsBase) {
  let retired = 0;
  const legacyDir = join(agentsBase, ".arkaos-legacy");
  for (const file of LEGACY_QG_PERSONA_FILES) {
    const deployedName = `arka-${file}`;
    const src = join(agentsBase, deployedName);
    if (!existsSync(src)) continue;
    try {
      mkdirSync(legacyDir, { recursive: true });
      let dest = join(legacyDir, deployedName);
      for (let n = 1; existsSync(dest); n++) {
        dest = join(legacyDir, `arka-${file.slice(0, -3)}-${n}.md`);
      }
      renameSync(src, dest);
      // Full resolved destination: this retirement moves files in the
      // user's HOME — the scope a reader is least able to guess.
      console.log(`         Retired v1 QG persona: ${deployedName} -> ${dest}`);
      retired++;
    } catch {
      // Best-effort — an unmovable persona stays in place, never deleted.
    }
  }
  return retired;
}

function deployDeptAgents(agentsSrc, agentsBase, written) {
  let deployed = 0;
  for (const file of readdirSync(agentsSrc)) {
    if (!file.endsWith(".md")) continue;
    if (LEGACY_QG_PERSONA_FILES.includes(file)) continue;
    const srcFile = join(agentsSrc, file);
    try {
      if (!statSync(srcFile).isFile()) continue;
    } catch {
      continue;
    }
    const target = `arka-${file.replace(/\.md$/, "")}.md`;
    copyFileSync(srcFile, join(agentsBase, target));
    written.add(target);
    deployed++;
  }
  return deployed;
}
