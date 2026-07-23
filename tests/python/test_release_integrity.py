"""Locking tests: release integrity.

Antidote to the v4.37.0/v4.38.0 incident — two npm releases shipped with
no CHANGELOG entry because nothing tied the file to VERSION, and the
OpenCode governance plugin exists as two copies (installer source +
generated harness) guarded only by regeneration. Both locks fail CI
instead of shipping silently.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _version() -> str:
    return (_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_changelog_top_entry_matches_version():
    changelog = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(?P<v>[^\]]+)\]", changelog, flags=re.MULTILINE)
    assert match, "CHANGELOG.md has no '## [x.y.z]' entry"
    assert match.group("v") == _version(), (
        f"CHANGELOG.md top entry is [{match.group('v')}] but VERSION is "
        f"{_version()} — document the release before (or with) the bump; "
        f"v4.37.0/v4.38.0 shipped undocumented and this lock exists so "
        f"that can never happen again."
    )


def test_opencode_plugin_copies_identical():
    source = _ROOT / "installer" / "assets" / "opencode" / "arka.ts"
    harness = _ROOT / "harness" / "opencode" / "plugins" / "arka.ts"
    assert source.is_file(), f"missing plugin source: {source}"
    assert harness.is_file(), f"missing generated harness copy: {harness}"
    assert source.read_bytes() == harness.read_bytes(), (
        "installer/assets/opencode/arka.ts and harness/opencode/plugins/"
        "arka.ts have drifted — run scripts/harness_gen.py to regenerate "
        "the harness copy from the installer source."
    )
