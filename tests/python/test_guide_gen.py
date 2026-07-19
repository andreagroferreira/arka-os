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


def test_guide_lists_every_real_command_prefix():
    # Checked against the registry DATA (command tokens), not against the
    # generator's own grouping — a dead prefix like the old /leadership
    # (label without a matching command) must never render.
    import json

    registry = json.loads(
        (REPO_ROOT / "knowledge" / "commands-registry.json").read_text(
            encoding="utf-8"
        )
    )
    tokens = {
        cmd["command"].split()[0]
        for cmd in registry["commands"]
        if str(cmd.get("command", "")).startswith("/")
    }
    guide = (REPO_ROOT / GUIDE_NAME).read_text(encoding="utf-8")
    missing = [t for t in sorted(tokens) if f"| `{t}` |" not in guide]
    assert missing == []
    assert "| `/leadership` |" not in guide


def _fixture_root(tmp_path):
    import json

    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "commands-registry.json").write_text(
        json.dumps({"commands": [
            {"command": "/dev feature", "department": "dev"},
            {"command": "/lead feedback", "department": "leadership"},
        ]}),
        encoding="utf-8",
    )
    return tmp_path


def test_main_happy_path_writes_guide_to_root(tmp_path):
    import guide_gen

    assert guide_gen.main(_fixture_root(tmp_path)) == 0
    guide = (tmp_path / GUIDE_NAME).read_text(encoding="utf-8")
    assert "v9.9.9" in guide
    assert "| `/lead` |" in guide
    assert "/leadership" not in guide


def test_main_over_budget_fails_closed_without_writing(tmp_path, monkeypatch):
    import guide_gen

    monkeypatch.setattr(guide_gen, "SIZE_BUDGET_BYTES", 100)
    root = _fixture_root(tmp_path)
    assert guide_gen.main(root) == 1
    assert not (root / GUIDE_NAME).exists()
