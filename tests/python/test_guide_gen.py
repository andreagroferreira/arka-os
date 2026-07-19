"""THE-ARKAOS-GUIDE.md is generated, never hand-edited, never bloated."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from guide_gen import GUIDE_NAME, SIZE_BUDGET_BYTES, render  # noqa: E402


def test_committed_guide_matches_fresh_regen():
    committed = (REPO_ROOT / GUIDE_NAME).read_text(encoding="utf-8")
    assert committed == render(REPO_ROOT), (
        "THE-ARKAOS-GUIDE.md drifted — regenerate with "
        "`arka-py scripts/guide_gen.py`, never hand-edit"
    )


def test_guide_carries_the_real_version():
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert f"v{version}" in (REPO_ROOT / GUIDE_NAME).read_text(encoding="utf-8")


def test_guide_respects_the_size_budget():
    # The documented anti-pattern is the unreadable mega-guide; the
    # budget is part of the product contract, not a suggestion.
    size = (REPO_ROOT / GUIDE_NAME).stat().st_size
    assert size <= SIZE_BUDGET_BYTES


def test_guide_lists_every_department():
    import json

    registry = json.loads(
        (REPO_ROOT / "knowledge" / "commands-registry.json").read_text(
            encoding="utf-8"
        )
    )
    departments = {
        cmd["department"] for cmd in registry["commands"] if cmd.get("department")
    }
    guide = (REPO_ROOT / GUIDE_NAME).read_text(encoding="utf-8")
    missing = [d for d in sorted(departments) if f"| `/{d}` |" not in guide]
    assert missing == []
