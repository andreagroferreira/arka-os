"""docs/SKILLS-CATALOG.md is generated, never hand-edited.

The complete skill surface (every department SKILL.md including the 17
hubs, plus the /arka meta skills) is compiled by
``scripts/skills_catalog_gen.py``. This lock keeps the committed file
byte-identical to a fresh run, so the catalog can never drift from the
SKILL.md tree it documents.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills_catalog_gen import _clean_description, generate  # noqa: E402

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


def test_trigger_cut_does_not_double_an_existing_full_stop():
    """A head that already ends in a full stop gets no second one.

    The TRIGGER: separator used to be injected unconditionally, so every
    description whose first sentence was properly terminated rendered with
    a stacked pair — 120 of them across the catalog.
    """
    for closer in (".", "!", "?"):
        raw = f"Ships the thing{closer} TRIGGER: when the user asks."
        assert _clean_description(raw, "fb") == f"Ships the thing{closer}"


def test_trigger_cut_still_closes_an_unterminated_head():
    """The separator is not removed, only made conditional.

    Cutting the TRIGGER: clause off an unterminated head leaves a dangling
    fragment, so the full stop must still be supplied there.
    """
    raw = "Ships the thing TRIGGER: when the user asks."
    assert _clean_description(raw, "fb") == "Ships the thing."


def test_dot_prefixed_tokens_keep_their_leading_space():
    """Filenames like .env and .gitignore are not welded to the word before.

    The " ." collapse was unanchored, so it matched the dot that OPENS a
    token as readily as the one that ENDS a sentence, producing
    "Management):.gitignore" and "keys,.env" in the shipped catalog.
    """
    raw = "Audit secrets (Management): .gitignore coverage, .env drift."
    out = _clean_description(raw, "fb")
    assert ": .gitignore coverage" in out
    assert ", .env drift." in out


def test_sentence_final_space_dot_is_still_collapsed():
    """The anchored collapse keeps working where the dot ends the text."""
    assert _clean_description("Ships the thing .", "fb") == "Ships the thing."
    assert _clean_description("Ships . Then stops.", "fb") == "Ships. Then stops."


def test_truncation_does_not_stack_a_full_stop_onto_the_ellipsis():
    """A cut landing on a sentence end yields "...", never "....".

    Same defect class as the TRIGGER: separator — punctuation stacked by
    mechanical assembly. One description shipped with four dots.
    """
    raw = "word " * 34 + "done. " + "more " * 10
    out = _clean_description(raw, "fb")
    assert out.endswith("done...")
    assert "...." not in out


def test_no_catalog_cell_ends_in_a_doubled_full_stop():
    """Repo-wide lock: `..` never terminates a description cell.

    `...` is the legitimate truncation marker; exactly two dots is always
    the separator bug. Anchoring on the table cell (`|`) is what the
    triage's first `\\.\\.$` grep missed — every row ends in " |".
    """
    doubled = [
        line for line in generate().splitlines()
        if re.search(r"(?:^|[^.])\.\.\s*\|$", line)
    ]
    assert not doubled, (
        "descriptions end in a doubled full stop:\n  "
        + "\n  ".join(doubled[:5])
    )
