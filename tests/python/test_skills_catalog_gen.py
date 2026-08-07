"""docs/SKILLS-CATALOG.md is generated, never hand-edited.

The complete skill surface (every department SKILL.md including the 17
hubs, plus the /arka meta skills) is compiled by
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
    """The headline must equal docs_stats, whatever the count happens to be.

    Derived, not pinned: the docs-as-code rule is that counts come from
    docs_stats.py and are never hand-typed. An earlier version hard-coded
    333 here, which made every added skill fail a test whose name promises
    a comparison rather than a constant.
    """
    from scripts.tools import docs_stats

    fresh = generate()
    expected = docs_stats.count_skills(REPO_ROOT)["core"]
    headline = [
        line for line in fresh.splitlines()
        if line.startswith(f"**{expected} skills**")
    ]
    assert headline, (
        f"catalog must open with the {expected}-skill headline that "
        "docs_stats reports; regenerate with scripts/skills_catalog_gen.py"
    )
