"""Agent roster locks — no gate owner may be a ghost (P0, 2026-07-12).

The specialist gate blocked a lead and told it to dispatch owners that
did not exist as dispatchable agents (4 of 7 were department YAML the
installer never ships). These locks make that class of dead end a
build-time failure forever.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agents import roster_manifest as rm  # noqa: E402


def test_committed_roster_is_byte_identical_to_generator():
    committed = rm.ROSTER_JSON.read_text(encoding="utf-8")
    assert committed == rm.render(), (
        "config/agent-roster.json drifted — run "
        "`python -m core.agents.roster_manifest` and commit"
    )


def test_every_ownership_owner_has_a_dispatchable_source():
    """The anti-ghost lock: fails the build the moment an ownership rule
    names an owner without a deployable agent definition."""
    roster = json.loads(rm.ROSTER_JSON.read_text(encoding="utf-8"))
    entries = roster["gate_owners"]
    for slug in rm.gate_owners():
        assert slug in entries, f"gate owner {slug!r} missing from roster"
        source = REPO_ROOT / entries[slug]["source"]
        assert source.is_file(), f"{slug}: source vanished ({source})"
        assert rm._frontmatter_name(source) == slug, (
            f"{slug}: source frontmatter name mismatch — the Task tool "
            f"resolves agents by that name"
        )


def test_generator_refuses_ghost_owners(tmp_path, monkeypatch):
    """An owner with no source anywhere must abort generation loudly."""
    ownership = tmp_path / "ownership.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - pattern: '**/x/**'\n"
        "    owners: [ghost-agent]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rm, "OWNERSHIP_YAML", ownership)
    with pytest.raises(ValueError, match="ghost-agent"):
        rm.build_roster()


def test_hand_authored_department_md_wins_over_compiled():
    """frontend-dev has BOTH a dept .md and a compiled .md — the
    hand-tuned department file must win (it is what ships today)."""
    roster = json.loads(rm.ROSTER_JSON.read_text(encoding="utf-8"))
    entry = roster["gate_owners"]["frontend-dev"]
    assert entry["source"].startswith("departments/")
    assert entry["compiled"] is False


def test_the_four_incident_ghosts_are_now_dispatchable():
    """Regression pin for the 2026-07-12 incident set."""
    roster = json.loads(rm.ROSTER_JSON.read_text(encoding="utf-8"))
    for slug in ("backend-dev", "dba", "devops-eng", "security-eng"):
        entry = roster["gate_owners"].get(slug)
        assert entry, f"{slug} lost its roster entry"
        assert (REPO_ROOT / entry["source"]).is_file()
