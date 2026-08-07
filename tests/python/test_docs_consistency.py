"""Locking test: documentation numbers must equal the canonical counter.

This is the antidote to documentation drift. README.md, CLAUDE.md, and
arka/SKILL.md all advertise the same headline counts (agents, departments,
skills). This test runs scripts/tools/docs_stats.py against the repo and
asserts every one of those documents carries the generated numbers — so a
future edit that hand-types a wrong number fails CI instead of shipping.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATS_PATH = _ROOT / "scripts" / "tools" / "docs_stats.py"


def _load_docs_stats():
    spec = importlib.util.spec_from_file_location("docs_stats_lock", _STATS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["docs_stats_lock"] = module
    spec.loader.exec_module(module)
    return module


_ds = _load_docs_stats()
_STATS = _ds.gather(_ds.repo_root())

_AGENTS = _STATS["agents"]["files"]          # 82
_DEPARTMENTS = _STATS["departments"]         # 17
_SKILLS = _STATS["skills"]["core"]           # 267
_PLUGINS = _STATS["skills"]["plugins"]       # marketplace pack skills


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_readme_carries_canonical_numbers():
    readme = _read("README.md")
    assert f"{_AGENTS} agents" in readme
    assert f"{_DEPARTMENTS} departments" in readme
    assert f"{_SKILLS} skills" in readme


def test_readme_carries_marketplace_pack_count():
    """The marketplace pack-skill total is hand-written prose, so it rots
    silently as the plugin export grows. Lock it to the generated number."""
    readme = _read("README.md")
    assert f"{_PLUGINS} skills" in readme, (
        f"README marketplace count is stale — plugins/ holds {_PLUGINS} "
        f"pack skills; update the 'department packs with N skills' line."
    )


def test_project_claude_md_carries_canonical_numbers():
    claude = _read("CLAUDE.md")
    assert f"{_AGENTS} agents" in claude
    assert f"{_DEPARTMENTS} departments" in claude
    assert f"{_SKILLS} skills" in claude


def test_arka_skill_header_carries_canonical_numbers():
    skill = _read("arka/SKILL.md")
    assert f"{_AGENTS} agents" in skill
    assert f"{_DEPARTMENTS} departments" in skill
    assert f"{_SKILLS} skills" in skill


def test_wiki_home_carries_canonical_numbers():
    home = _read("wiki/Home.md")
    assert f"{_AGENTS} agents" in home
    assert f"{_DEPARTMENTS} departments" in home


def test_no_retired_numbers_in_primary_docs():
    """The known-bad drift values must not reappear in the primary surfaces."""
    surfaces = ["README.md", "CLAUDE.md", "arka/SKILL.md", "wiki/Home.md"]
    retired = ["65 agents", "106 agents", "56 agents", "244+ skills",
               "8-layer", "9-layer", "379 token"]
    for rel in surfaces:
        text = _read(rel)
        for bad in retired:
            assert bad not in text, f"retired value {bad!r} found in {rel}"


def test_version_is_aligned_across_manifests():
    version = _STATS["version"]
    assert version  # non-empty
    assert (_ROOT / "package.json").read_text(encoding="utf-8").count(f'"{version}"') >= 1
    assert version in (_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_no_doc_carries_a_superseded_skill_count():
    """No prose surface may assert a skill count docs_stats disagrees with.

    The repo-wide replacement for a tripwire that used to exist by
    accident: a literal `333` pinned inside
    tests/python/test_skills_catalog_gen.py failed on any added skill and
    so caught stale prose everywhere. Deriving that assertion (correct in
    itself) removed the alarm, and the same PR shipped nine stale counts
    across seven files while all eighteen docs locks stayed green — one
    wiki page held both 333 and 334 at once.

    Scope: hand-written Markdown and the scripts that generate prose.
    Excluded by design, because each states what was true when written and
    must keep its figures: CHANGELOG.md, docs/adr/, and the dated
    implementation plans and specs under docs/superpowers/. Also excluded:
    docs/.work/ (untracked scratch that declares itself unpublishable) and
    docs/SKILLS-CATALOG.md, which is generated and drift-gated against its
    own source. harness/, plugins/ and marketplace/ are outside the roots
    walked here for the same generated-artifact reason.
    """
    import re

    current = {
        _STATS["skills"]["core"],
        _STATS["skills"]["departments"],
        _STATS["skills"]["plugins"],
    }
    # prompt_lint.py is excluded because its data IS a list of retired
    # counts: it exists to ban them, so finding them there is the tool
    # working, not prose drifting.
    skip_names = {"SKILLS-CATALOG.md", "CHANGELOG.md", "prompt_lint.py"}
    skip_dirs = {"adr", ".work", "plans", "specs"}
    files = [_ROOT / "README.md", _ROOT / "CLAUDE.md", _ROOT / "CONTRIBUTING.md",
             _ROOT / "arka" / "SKILL.md"]
    for root in (_ROOT / "wiki", _ROOT / "docs", _ROOT / "scripts"):
        if not root.is_dir():
            continue
        for path in [*root.rglob("*.md"), *root.rglob("*.py")]:
            if path.name in skip_names or skip_dirs & set(path.parts):
                continue
            files.append(path)

    # `(?<![~\d])` lets an explicit approximation ("~200 skills") through:
    # it claims a magnitude, not a count, and does not go stale.
    pattern = re.compile(
        r"(?<![~\d])\b(\d{3})\s+"
        r"(?:core\s+|department\s+|plugin\s+|non-curated\s+)?skills?\b"
    )
    offenders = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            value = int(match.group(1))
            # Only judge numbers in the plausible band; unrelated
            # three-digit figures (ports, years, token counts) are not
            # skill counts even when a noun follows.
            if 150 <= value <= 999 and value not in current:
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(_ROOT)}:{line} says {match.group(0)!r}")
    assert not offenders, (
        "these surfaces assert a skill count docs_stats does not report "
        f"({sorted(current)}); regenerate or correct them:\n  "
        + "\n  ".join(offenders)
    )
