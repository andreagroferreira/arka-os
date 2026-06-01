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


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_readme_carries_canonical_numbers():
    readme = _read("README.md")
    assert f"{_AGENTS} agents" in readme
    assert f"{_DEPARTMENTS} departments" in readme
    assert f"{_SKILLS} skills" in readme


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
