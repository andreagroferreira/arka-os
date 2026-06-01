"""Tests for scripts/tools/docs_stats.py -- the canonical documentation
source-of-truth counter. Deterministic counts run against a synthetic fixture
tree; a smoke test asserts plausibility against the real repo.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "tools" / "docs_stats.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("docs_stats", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["docs_stats"] = module
    spec.loader.exec_module(module)
    return module


docs_stats = _load()


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A minimal repo tree with known, deterministic counts."""
    (tmp_path / "VERSION").write_text("4.0.0\n", encoding="utf-8")
    # dev: 2 agents (a, b), 1 skill
    (tmp_path / "departments/dev/agents").mkdir(parents=True)
    (tmp_path / "departments/dev/agents/a.yaml").write_text("id: a", encoding="utf-8")
    (tmp_path / "departments/dev/agents/b.yaml").write_text("id: b", encoding="utf-8")
    (tmp_path / "departments/dev/skills/feat").mkdir(parents=True)
    (tmp_path / "departments/dev/skills/feat/SKILL.md").write_text("# feat", encoding="utf-8")
    # dev sub-squad: 1 nested agent (recursive globbing must find it)
    (tmp_path / "departments/dev/agents/backend-core").mkdir(parents=True)
    (tmp_path / "departments/dev/agents/backend-core/c.yaml").write_text("id: c", encoding="utf-8")
    # mkt: 1 agent reusing slug a.yaml (matrix cross-listing), 1 skill
    (tmp_path / "departments/mkt/agents").mkdir(parents=True)
    (tmp_path / "departments/mkt/agents/a.yaml").write_text("id: a", encoding="utf-8")
    (tmp_path / "departments/mkt/skills/grow").mkdir(parents=True)
    (tmp_path / "departments/mkt/skills/grow/SKILL.md").write_text("# grow", encoding="utf-8")
    # arka: 1 skill
    (tmp_path / "arka/skills/do").mkdir(parents=True)
    (tmp_path / "arka/skills/do/SKILL.md").write_text("# do", encoding="utf-8")
    # 2 ADRs
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "docs/adr/0001.md").write_text("# adr", encoding="utf-8")
    (tmp_path / "docs/adr/0002.md").write_text("# adr", encoding="utf-8")
    # tests: 3 test functions (2 sync, 1 async)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_sample.py").write_text(
        "def test_one():\n    pass\n"
        "def test_two():\n    pass\n"
        "async def test_three():\n    pass\n",
        encoding="utf-8",
    )
    return tmp_path


def test_count_agents_files_and_unique_slugs(fake_repo):
    result = docs_stats.count_agents(fake_repo)
    # dev: a, b, backend-core/c (nested) + mkt: a (cross-listed) = 4 files
    assert result["files"] == 4
    assert result["unique_slugs"] == 3  # a.yaml cross-listed in dev + mkt


def test_count_departments(fake_repo):
    assert docs_stats.count_departments(fake_repo) == 2


def test_count_skills(fake_repo):
    skills = docs_stats.count_skills(fake_repo)
    assert skills["departments"] == 2
    assert skills["arka"] == 1
    assert skills["core"] == 3


def test_count_adrs(fake_repo):
    assert docs_stats.count_adrs(fake_repo) == 2


def test_count_test_functions_includes_async(fake_repo):
    assert docs_stats.count_test_functions(fake_repo) == 3


def test_read_version(fake_repo):
    assert docs_stats.read_version(fake_repo) == "4.0.0"


def test_gather_returns_serialisable_dict(fake_repo):
    stats = docs_stats.gather(fake_repo)
    assert stats["version"] == "4.0.0"
    assert stats["agents"]["files"] == 4
    assert stats["departments"] == 2
    assert stats["skills"]["core"] == 3
    assert stats["adrs"] == 2
    assert stats["tests"]["functions"] == 3
    import json

    json.dumps(stats)  # must be JSON-serialisable


def test_repo_root_autodetect_from_fixture(fake_repo):
    found = docs_stats.repo_root(fake_repo / "departments" / "dev")
    assert found == fake_repo


# --- Smoke test against the real repository ---------------------------------


def test_real_repo_plausibility():
    root = docs_stats.repo_root()
    stats = docs_stats.gather(root)
    assert stats["version"]  # non-empty
    assert stats["departments"] == 17
    assert stats["agents"]["files"] >= 80
    assert stats["skills"]["core"] >= 250
    assert stats["adrs"] >= 9
    # Deliberate lower-bound floor (actual ~2780): asserts "the counter found
    # the test suite" without flaking as tests are added or removed.
    assert stats["tests"]["functions"] >= 2000
