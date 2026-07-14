"""The distribution surface must be provably generated, not just claimed.

``marketplace/skills/`` holds ten exported copies of ``departments/dev``
skills and ships in the npm tarball. ``scripts/marketplace_export.py``
writes them — but nothing asserted that the committed tree is what the
generator would emit. A hand-edit there (or a third-party skill dropped
in) would ship, and the provenance classifier deliberately skips the
tree on the grounds that it is generated. That exclusion is only honest
if the claim is enforced.

``plugins/`` already has this gate (``test_marketplace_gen.py``). This
is the same lock on the other generated tree, and it is what lets
``test_skill_provenance.py`` exclude both: the sources are classified,
and the copies provably come from the sources.
"""

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).parent.parent.parent
if str(BASE_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "scripts"))

from marketplace_export import (  # noqa: E402
    EXPORTABLE_SKILLS,
    SOURCE_DIR,
    _convert,
)

EXPORT_DIR = BASE_DIR / "marketplace" / "skills"


@pytest.mark.parametrize("slug", EXPORTABLE_SKILLS)
def test_committed_export_matches_a_fresh_one(slug):
    """Byte-for-byte, the committed copy is what the generator emits."""
    source = (SOURCE_DIR / slug / "SKILL.md").read_text(encoding="utf-8")
    committed = (EXPORT_DIR / slug / "SKILL.md").read_text(encoding="utf-8")
    assert committed == _convert(source), (
        f"marketplace/skills/{slug}/SKILL.md has drifted from "
        f"departments/dev/skills/{slug} — run "
        f"scripts/marketplace_export.py, and never hand-edit the export"
    )


def test_export_tree_holds_nothing_unexported():
    """No skill may exist in the export that the generator did not put
    there — that is exactly how an unclassified port would ship."""
    on_disk = {d.name for d in EXPORT_DIR.iterdir() if d.is_dir()}
    assert on_disk == set(EXPORTABLE_SKILLS), (
        f"marketplace/skills/ holds directories the generator does not "
        f"emit: {sorted(on_disk - set(EXPORTABLE_SKILLS))}"
    )
