"""docs/SKILLS-CATALOG.md is generated, never hand-edited.

The complete skill surface (333 SKILL.md files: 318 department skills
including the 17 hubs, plus 15 /arka meta skills) is compiled by
``scripts/skills_catalog_gen.py``. This lock keeps the committed file
byte-identical to a fresh run, so the catalog can never drift from the
SKILL.md tree it documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills_catalog_gen import generate  # noqa: E402

CATALOG = REPO_ROOT / "docs" / "SKILLS-CATALOG.md"


def test_committed_catalog_matches_fresh_regen():
    fresh = generate()
    committed = CATALOG.read_text(encoding="utf-8")
    assert fresh == committed, (
        "docs/SKILLS-CATALOG.md drifted — regenerate with "
        "python scripts/skills_catalog_gen.py"
    )


def test_catalog_headline_matches_docs_stats():
    from scripts.tools import docs_stats  # noqa: PLC0415

    fresh = generate()
    headline = [l for l in fresh.splitlines() if l.startswith("**333 skills**")]
    assert headline, "catalog must open with the 333 headline"
    skills = docs_stats.count_skills(REPO_ROOT)
    assert skills["core"] == 333, "docs_stats must agree with the catalog"
