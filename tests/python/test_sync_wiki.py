"""Tests for scripts/tools/sync_wiki.py -- the wiki/ -> GitHub Wiki transformer.

The GitHub Wiki is flat (no subdirectories) and references pages by name
without the .md extension. This transformer flattens wiki/04-Departments/*
into prefixed page names and rewrites every internal link accordingly, while
turning ../docs/ links into absolute repo URLs. All transformations are pure
and deterministic, so they are fully unit-tested here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[2] / "scripts" / "tools" / "sync_wiki.py"


def _load():
    spec = importlib.util.spec_from_file_location("sync_wiki", _MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_wiki"] = mod
    spec.loader.exec_module(mod)
    return mod


sw = _load()

REPO = "https://github.com/andreagroferreira/arka-os"


# --- page-name flattening ---------------------------------------------------

@pytest.mark.parametrize("rel,expected", [
    ("Home.md", "Home"),
    ("01-Getting-Started.md", "01-Getting-Started"),
    ("16-Configuration.md", "16-Configuration"),
    ("04-Departments/README.md", "04-Departments"),
    ("04-Departments/dev.md", "04-Departments-dev"),
    ("04-Departments/quality.md", "04-Departments-quality"),
])
def test_page_name(rel, expected):
    assert sw.page_name(rel) == expected


# --- link rewriting ---------------------------------------------------------

def _name_map(files):
    return {f: sw.page_name(f) for f in files}


WIKI_FILES = [
    "Home.md", "01-Getting-Started.md", "02-Core-Concepts.md",
    "03-The-13-Phase-Flow.md", "11-Benchmarks.md",
    "04-Departments/README.md", "04-Departments/dev.md", "04-Departments/pm.md",
]


def test_rewrite_sibling_root_link():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("see [start](01-Getting-Started.md) now", "Home.md", nm, REPO)
    assert "[start](01-Getting-Started)" in out


def test_rewrite_dir_index_link():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[depts](04-Departments/)", "Home.md", nm, REPO)
    assert "[depts](04-Departments)" in out


def test_rewrite_parent_link_from_subdir():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[home](../Home.md)", "04-Departments/dev.md", nm, REPO)
    assert "[home](Home)" in out


def test_rewrite_sibling_in_subdir():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[pm](pm.md)", "04-Departments/dev.md", nm, REPO)
    assert "[pm](04-Departments-pm)" in out


def test_rewrite_docs_link_becomes_absolute():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[arch](../docs/ARCHITECTURE.md)", "Home.md", nm, REPO)
    assert f"{REPO}/blob/master/docs/ARCHITECTURE.md" in out


def test_external_link_untouched():
    nm = _name_map(WIKI_FILES)
    text = "[claude](https://claude.ai/code)"
    assert sw.rewrite_links(text, "Home.md", nm, REPO) == text


def test_anchor_preserved_on_internal_link():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[x](11-Benchmarks.md#routing)", "Home.md", nm, REPO)
    assert "[x](11-Benchmarks#routing)" in out


def test_rewrite_titled_link_strips_md_keeps_title():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links('[x](01-Getting-Started.md "Get going")', "Home.md", nm, REPO)
    assert '[x](01-Getting-Started "Get going")' in out


def test_links_inside_fenced_code_untouched():
    nm = _name_map(WIKI_FILES)
    src = "real [a](01-Getting-Started.md)\n```\nexample [b](01-Getting-Started.md)\n```\n"
    out = sw.rewrite_links(src, "Home.md", nm, REPO)
    assert "[a](01-Getting-Started)" in out          # real link rewritten
    assert "[b](01-Getting-Started.md)" in out        # fenced example preserved


def test_links_inside_inline_code_untouched():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("run `[b](01-Getting-Started.md)` here", "Home.md", nm, REPO)
    assert "`[b](01-Getting-Started.md)`" in out


def test_external_link_with_parens_not_truncated():
    nm = _name_map(WIKI_FILES)
    text = "[wiki](https://en.wikipedia.org/wiki/Foo_(bar))"
    assert sw.rewrite_links(text, "Home.md", nm, REPO) == text


def test_image_link_left_alone_when_external():
    nm = _name_map(WIKI_FILES)
    text = "![diagram](https://example.com/x.png)"
    assert sw.rewrite_links(text, "Home.md", nm, REPO) == text


def test_branch_param_in_absolute_docs_link():
    nm = _name_map(WIKI_FILES)
    out = sw.rewrite_links("[a](../docs/X.md)", "Home.md", nm, REPO, branch="main")
    assert f"{REPO}/blob/main/docs/X.md" in out


def test_sidebar_generated(tmp_path):
    src = tmp_path / "wiki"
    (src / "04-Departments").mkdir(parents=True)
    (src / "Home.md").write_text("# H", encoding="utf-8")
    (src / "01-Getting-Started.md").write_text("# GS", encoding="utf-8")
    (src / "04-Departments" / "README.md").write_text("# idx", encoding="utf-8")
    (src / "04-Departments" / "dev.md").write_text("# dev", encoding="utf-8")
    out = tmp_path / "out"
    sw.build_wiki(src, out, REPO)
    sidebar = (out / "_Sidebar.md").read_text(encoding="utf-8")
    assert "[[Home]]" in sidebar
    assert "[[01-Getting-Started]]" in sidebar
    assert "[[04-Departments]]" in sidebar       # the index page is listed
    assert "[[04-Departments-dev]]" in sidebar
    assert "### Departments" in sidebar


def test_build_wiki_writes_flat_pages(tmp_path):
    src = tmp_path / "wiki"
    (src / "04-Departments").mkdir(parents=True)
    (src / "Home.md").write_text("[d](04-Departments/dev.md)", encoding="utf-8")
    (src / "04-Departments" / "README.md").write_text("# Index", encoding="utf-8")
    (src / "04-Departments" / "dev.md").write_text("[home](../Home.md)", encoding="utf-8")
    out = tmp_path / "out"
    pages = sw.build_wiki(src, out, REPO)
    # flat output, no subdirectories
    assert (out / "Home.md").exists()
    assert (out / "04-Departments-dev.md").exists()
    assert (out / "04-Departments.md").exists()
    assert not (out / "04-Departments").is_dir()
    # links rewritten in output
    assert "[d](04-Departments-dev)" in (out / "Home.md").read_text(encoding="utf-8")
    assert "[home](Home)" in (out / "04-Departments-dev.md").read_text(encoding="utf-8")
    assert pages >= 3
