"""Tests for the cross-department matrix squads (missions + transversal).

These implement "Autonomy by Missions, not Departments". Unlike the existing
department-squad tests, this suite also cross-checks every member agent_id
against the real agent roster so a squad can never reference a ghost agent.
"""

import json
import os
import re
from pathlib import Path

import pytest

from core.squads.loader import load_matrix_squads
from core.squads.schema import SquadType, TeamTopologyType

REPO_ROOT = Path(__file__).parent.parent.parent
SQUADS_DIR = REPO_ROOT / "squads"
REGISTRY = REPO_ROOT / "knowledge" / "agents-registry-v2.json"
VAULT = Path(os.path.expanduser("~/Documents/Personal"))
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _agent_ids() -> set[str]:
    data = json.loads(REGISTRY.read_text())
    return {a["id"] for a in data["agents"]}


MATRIX_SQUADS = load_matrix_squads(SQUADS_DIR)
AGENT_IDS = _agent_ids()


def test_matrix_squads_exist():
    ids = {s.id for s in MATRIX_SQUADS}
    expected = {
        "mission-acquire", "mission-activate", "mission-retain", "mission-recover",
        "transversal-revops", "transversal-people-org", "transversal-governance",
    }
    assert expected <= ids, f"missing matrix squads: {expected - ids}"


@pytest.mark.parametrize("squad", MATRIX_SQUADS, ids=lambda s: s.id)
def test_squad_well_formed(squad):
    assert squad.id and squad.name and squad.description
    assert squad.size >= 1
    assert squad.has_lead, f"{squad.id} has no lead"
    assert squad.size <= squad.max_size


@pytest.mark.parametrize("squad", MATRIX_SQUADS, ids=lambda s: s.id)
def test_members_reference_real_agents(squad):
    for member in squad.members:
        assert member.agent_id in AGENT_IDS, (
            f"{squad.id} references unknown agent '{member.agent_id}'"
        )


@pytest.mark.parametrize("squad", MATRIX_SQUADS, ids=lambda s: s.id)
def test_cross_department_members_are_borrowed(squad):
    # Matrix squads borrow from home departments — every member should declare it.
    for member in squad.members:
        assert member.borrowed, f"{squad.id}:{member.agent_id} must be borrowed"
        assert member.source_department, (
            f"{squad.id}:{member.agent_id} missing source_department"
        )


def test_missions_are_stream_aligned_projects():
    missions = [s for s in MATRIX_SQUADS if s.id.startswith("mission-")]
    assert len(missions) == 4
    for m in missions:
        assert m.squad_type == SquadType.PROJECT
        assert m.topology == TeamTopologyType.STREAM_ALIGNED


def test_transversal_squads_are_platform_or_enabling():
    transversal = [s for s in MATRIX_SQUADS if s.id.startswith("transversal-")]
    assert len(transversal) == 3
    for t in transversal:
        assert t.squad_type in (SquadType.PLATFORM, SquadType.ENABLING)


def _vault_basenames() -> set[str]:
    return {p.stem for p in VAULT.rglob("*.md") if ".trash" not in p.parts}


@pytest.mark.skipif(not VAULT.exists(), reason="Obsidian vault not present (CI)")
@pytest.mark.parametrize("squad", MATRIX_SQUADS, ids=lambda s: s.id)
def test_kb_wikilinks_resolve(squad):
    # KB-grounding must be real: every [[wikilink]] in a squad description must
    # resolve to an existing vault note (by basename, like Obsidian does).
    basenames = _vault_basenames()
    for link in WIKILINK_RE.findall(squad.description):
        base = link.split("|")[0].split("/")[-1].strip()
        assert base in basenames, f"{squad.id} cites missing KB note '[[{link}]]'"
