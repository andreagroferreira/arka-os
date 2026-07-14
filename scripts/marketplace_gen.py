"""Marketplace generator — per-department plugins from the curated cut.

F2-7b (ruflo-teardown campaign, distribution endgame): the ArkaOS
marketplace answers ruflo's 38-plugin distribution surface WITHOUT its
344-SKILL.md context blowout. The curated core stays on the installer
channel (multi-runtime); every sub-skill OUTSIDE the curated set ships
à la carte in a per-department plugin, where the plugin namespace
(``arkaos-<dept>:<skill>``) also disambiguates the later-wins collision
slugs natively.

Single source of truth: ``config/skills-curated.yaml`` + the
``departments/`` tree. This script GENERATES (never hand-typed —
docs_stats/gate_manifest precedent):

- ``plugins/arkaos-<dept>/`` — one plugin per department with a
  non-empty complement (dept sub-skills minus curated), skills exported
  with the marketplace transformations;
- ``.claude-plugin/marketplace.json`` — EXTENDED, never replaced: the
  ``name``/``owner`` fields and the legacy ``arkaos-dev-skills`` entry
  are preserved verbatim (that plugin may already be installed on user
  machines and its 10-skill list is locked by
  ``test_marketplace_export.py``); top-level ``version`` tracks the
  VERSION file (kills the stale ``metadata.version`` for good);
- ``knowledge/skills-manifest.json`` — slug -> {depts, curated,
  plugins, collision} map consumed by /do install hints, the doctor and
  the F2-7c skill-budget linter.

Regenerate + commit after touching the YAML, any SKILL.md set, or
VERSION:

    python scripts/marketplace_gen.py

``tests/python/test_marketplace_gen.py`` drift-gates the committed tree
against a fresh in-memory run, byte for byte.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from marketplace_export import _convert  # noqa: E402

from core.skills.provenance import (  # noqa: E402
    FIRST_PARTY,
    SkillProvenance,
    parse_provenance,
)

CURATED_YAML = REPO_ROOT / "config" / "skills-curated.yaml"
DEPARTMENTS_DIR = REPO_ROOT / "departments"
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_MANIFEST_JSON = REPO_ROOT / "knowledge" / "skills-manifest.json"
VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

MARKETPLACE_NAME = "arkaos"
LEGACY_PLUGIN = "arkaos-dev-skills"
_RESOURCE_DIRS = ("scripts", "references", "assets")

# The export _convert strips slash-command suffixes but lets markdown
# links to ArkaOS commands through (observed leak:
# "[Browser Integration Pattern](/arka)" in marketplace/skills/
# code-review). Fifth transformation: unwrap them to plain text.
_ARKA_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(/arka[^)]*\)")

_DEPT_LABELS = {
    "brand": "Brand & Design",
    "community": "Communities & Groups",
    "content": "Content & Viralization",
    "dev": "Development",
    "ecom": "E-Commerce",
    "finance": "Finance & Investment",
    "kb": "Knowledge Management",
    "landing": "Landing Pages & Funnels",
    "leadership": "Leadership & People",
    "marketing": "Marketing & Growth",
    "ops": "Operations & Automation",
    "org": "Organization & Teams",
    "pm": "Project Management",
    "quality": "Quality",
    "saas": "SaaS & Micro-SaaS",
    "sales": "Sales & Negotiation",
    "strategy": "Strategy & Innovation",
}


def load_curated() -> dict[str, list[str]]:
    config = yaml.safe_load(CURATED_YAML.read_text(encoding="utf-8"))
    return {
        dept: sorted(slugs)
        for dept, slugs in config["curated_subskills"].items()
    }


def dept_subskills() -> dict[str, list[str]]:
    """All sub-skill slugs per department, from disk."""
    result: dict[str, list[str]] = {}
    for dept_dir in sorted(DEPARTMENTS_DIR.iterdir()):
        skills_dir = dept_dir / "skills"
        if not skills_dir.is_dir():
            continue
        slugs = sorted(
            p.name for p in skills_dir.iterdir()
            if (p / "SKILL.md").is_file()
        )
        if slugs:
            result[dept_dir.name] = slugs
    return result


def collision_slugs(subskills: dict[str, list[str]]) -> dict[str, list[str]]:
    """Slugs owned by more than one department (later-wins on deploy)."""
    owners: dict[str, list[str]] = {}
    for dept, slugs in subskills.items():
        for slug in slugs:
            owners.setdefault(slug, []).append(dept)
    return {s: sorted(d) for s, d in owners.items() if len(d) > 1}


_NAME_LINE_PATTERN = re.compile(r"^name:\s*.*$", flags=re.MULTILINE)


def convert_skill(body: str, slug: str) -> str:
    """The 4 marketplace_export transformations + two plugin-specific
    ones: unwrap markdown links to ArkaOS commands, and FORCE the
    frontmatter name to the directory slug — the in-tree files carry
    `name: <dept>/<name>` (235 of 265) and sometimes a name that is not
    the dir slug at all (`logo` in `logo-brief/`); the plugin runtime
    rejects name/dir mismatches."""
    out = _ARKA_LINK_PATTERN.sub(r"\1", _convert(body))
    return _NAME_LINE_PATTERN.sub(f"name: {slug}", out, count=1)


def _plugin_description(dept: str, slugs: list[str]) -> str:
    label = _DEPT_LABELS.get(dept, dept.title())
    shown = ", ".join(slugs[:8])
    more = f", +{len(slugs) - 8} more" if len(slugs) > 8 else ""
    return (
        f"ArkaOS {label} skills, à la carte — {len(slugs)} framework-backed "
        f"skills beyond the curated core: {shown}{more}. Generated by "
        f"scripts/marketplace_gen.py from departments/{dept}/skills/."
    )


def _emit_skill(src_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    body = (src_dir / "SKILL.md").read_text(encoding="utf-8")
    (dest_dir / "SKILL.md").write_text(
        convert_skill(body, dest_dir.name), encoding="utf-8")
    for resource in _RESOURCE_DIRS:
        src = src_dir / resource
        if src.is_dir():
            shutil.copytree(
                src, dest_dir / resource, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )


def build_plugins() -> dict[str, list[str]]:
    """Write plugins/arkaos-<dept>/ trees. Returns dept -> plugin slugs."""
    curated = load_curated()
    subskills = dept_subskills()
    if PLUGINS_DIR.exists():
        shutil.rmtree(PLUGINS_DIR)
    emitted: dict[str, list[str]] = {}
    for dept, slugs in subskills.items():
        complement = [s for s in slugs if s not in set(curated.get(dept, []))]
        if not complement:
            continue
        plugin_dir = PLUGINS_DIR / f"arkaos-{dept}"
        for slug in complement:
            _emit_skill(
                DEPARTMENTS_DIR / dept / "skills" / slug,
                plugin_dir / "skills" / slug,
            )
        _write_plugin_manifest(plugin_dir, dept, complement)
        emitted[dept] = complement
    return emitted


def _write_plugin_manifest(
    plugin_dir: Path, dept: str, slugs: list[str]
) -> None:
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    plugin_json = {
        "name": f"arkaos-{dept}",
        "description": _plugin_description(dept, slugs),
        # Version lives ONLY here (plugin.json wins silently over a
        # marketplace-entry version per the plugin spec — never both).
        "version": VERSION,
        "author": {"name": "WizardingCode", "email": "hello@wizardingcode.io"},
        "license": "MIT",
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_marketplace(emitted: dict[str, list[str]]) -> dict:
    """Extend the existing manifest — name/owner/legacy entry verbatim."""
    manifest = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    if manifest.get("name") != MARKETPLACE_NAME:
        raise ValueError(
            f"marketplace name changed ({manifest.get('name')!r}) — the "
            f"registered name is load-bearing on user machines; refusing"
        )
    legacy = [p for p in manifest["plugins"] if p.get("name") == LEGACY_PLUGIN]
    if len(legacy) != 1:
        raise ValueError("legacy arkaos-dev-skills entry missing — refusing")
    # Top-level version tracks VERSION (metadata.version is deprecated
    # upstream; the metadata KEY stays one release for backwards
    # compatibility, but its value tracks VERSION too — the stale 2.71.0
    # it carried was exactly the hand-typed drift this generator kills).
    manifest["version"] = VERSION
    if isinstance(manifest.get("metadata"), dict):
        manifest["metadata"]["version"] = VERSION
    dept_entries = [
        {
            "name": f"arkaos-{dept}",
            "source": f"./plugins/arkaos-{dept}",
            "category": dept,
            "description": _plugin_description(dept, slugs),
        }
        for dept, slugs in sorted(emitted.items())
    ]
    manifest["plugins"] = legacy + dept_entries
    return manifest


def skill_provenance(dept: str, slug: str) -> SkillProvenance:
    """Provenance from the skill's own frontmatter, path-tagged on error.

    A bare pydantic traceback across 260 skills is a needle hunt on the
    release-critical path (step 1b) — name the file that broke.
    """
    skill_md = DEPARTMENTS_DIR / dept / "skills" / slug / "SKILL.md"
    try:
        return parse_provenance(skill_md.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(
            f"{skill_md.relative_to(REPO_ROOT)}: bad provenance — {exc}"
        ) from exc


def _provenance_entry(prov: SkillProvenance) -> dict:
    """Manifest shape: the full licence trail, not just the origin."""
    entry = {"origin": prov.origin}
    if not prov.is_first_party:
        entry["source"] = prov.source
        entry["license"] = prov.license
    return entry


def _merge_provenance(slug: str, entry: dict, prov: SkillProvenance) -> None:
    """One manifest row can front N department copies of a slug.

    A collision where the copies disagree on lineage is unrepresentable
    in one row — refuse loudly rather than pick a winner.
    """
    incoming = _provenance_entry(prov)
    current = entry["provenance"]
    if current["origin"] == FIRST_PARTY:
        entry["provenance"] = incoming
        return
    if incoming["origin"] != FIRST_PARTY and incoming != current:
        raise ValueError(
            f"slug {slug!r} collides across departments with conflicting "
            f"provenance: {current} vs {incoming}"
        )


def _skill_rows(emitted: dict[str, list[str]]) -> dict[str, dict]:
    """slug -> {depts, curated, plugins, collision, provenance}."""
    curated = load_curated()
    subskills = dept_subskills()
    collisions = collision_slugs(subskills)
    skills: dict[str, dict] = {}
    for dept, slugs in subskills.items():
        for slug in slugs:
            entry = skills.setdefault(slug, {
                "depts": [], "curated": False, "plugins": [],
                "collision": slug in collisions,
                "provenance": {"origin": FIRST_PARTY},
            })
            entry["depts"].append(dept)
            _merge_provenance(slug, entry, skill_provenance(dept, slug))
            if slug in set(curated.get(dept, [])):
                entry["curated"] = True
            elif dept in emitted and slug in emitted[dept]:
                entry["plugins"].append(f"arkaos-{dept}@{MARKETPLACE_NAME}")
    for entry in skills.values():
        entry["depts"].sort()
        entry["plugins"].sort()
    return skills


def build_skills_manifest(emitted: dict[str, list[str]]) -> dict:
    skills = _skill_rows(emitted)
    return {
        "_meta": {
            "generator": "scripts/marketplace_gen.py",
            "version": VERSION,
            "marketplace": MARKETPLACE_NAME,
        },
        "structural": _structural_surface(),
        "skills": dict(sorted(skills.items())),
    }


def _structural_surface() -> dict:
    return {
        "main": "arka",
        "hubs": sorted(
            f"arka-{d.name}" for d in DEPARTMENTS_DIR.iterdir()
            if (d / "SKILL.md").is_file()
        ),
        "meta": sorted(
            f"arka-{p.name}" for p in (REPO_ROOT / "arka" / "skills").iterdir()
            if (p / "SKILL.md").is_file()
        ),
    }


def generate() -> dict:
    """Full generation. Returns summary counts for the CLI output."""
    emitted = build_plugins()
    marketplace = build_marketplace(emitted)
    MARKETPLACE_JSON.write_text(
        json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    skills_manifest = build_skills_manifest(emitted)
    SKILLS_MANIFEST_JSON.write_text(
        json.dumps(skills_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "plugins": len(emitted),
        "plugin_skills": sum(len(s) for s in emitted.values()),
        "curated": sum(len(s) for s in load_curated().values()),
        "collisions": len(collision_slugs(dept_subskills())),
    }


def main() -> int:
    summary = generate()
    print(
        f"marketplace generated: {summary['plugins']} dept plugins, "
        f"{summary['plugin_skills']} plugin skills, "
        f"{summary['curated']} curated in core, "
        f"{summary['collisions']} collision slugs (plugin-namespaced)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
