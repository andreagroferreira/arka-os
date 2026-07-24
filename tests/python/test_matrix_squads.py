"""Tests for the cross-department matrix squads (missions + transversal).

These implement "Autonomy by Missions, not Departments". Unlike the existing
department-squad tests, this suite also cross-checks every member agent_id
against the real agent roster so a squad can never reference a ghost agent.
"""

import json
import os
import re
import unicodedata
from pathlib import Path

import pytest

from core.squads.loader import load_matrix_squads
from core.squads.schema import SquadType, TeamTopologyType

REPO_ROOT = Path(__file__).parent.parent.parent
SQUADS_DIR = REPO_ROOT / "squads"
REGISTRY = REPO_ROOT / "knowledge" / "agents-registry-v2.json"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _resolve_vault() -> Path | None:
    """Canonical vault resolution (SPEC-paths-portability): env wins, then
    profile.json ``vaultPath``. Returns None when unconfigured so the
    wikilink tests skip instead of probing a stale location — the old
    ``~/Documents/Personal`` hardcode kept red-flagging every local QG
    after the operator moved the vault (7 false FAILs, 2026-07-24)."""
    env = os.environ.get("ARKAOS_VAULT_PATH")
    if env:
        return Path(env).expanduser()
    try:
        from core.runtime.path_resolver import load_profile

        value = load_profile().vault_path
    except Exception:
        return None
    return Path(value).expanduser() if value else None


VAULT = _resolve_vault()


def _agent_ids() -> set[str]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
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
    # NFC-normalize: macOS filesystems store accented names decomposed (NFD),
    # while YAML wikilinks are composed (NFC) — Obsidian resolves both, so
    # the test must too ("Missões" failed as a ghost until 2026-07-24).
    return {
        unicodedata.normalize("NFC", p.stem)
        for p in VAULT.rglob("*.md")
        if ".trash" not in p.parts
    }


@pytest.mark.skipif(
    VAULT is None or not VAULT.exists(),
    reason="Obsidian vault not configured/present (CI)",
)
@pytest.mark.parametrize("squad", MATRIX_SQUADS, ids=lambda s: s.id)
def test_kb_wikilinks_resolve(squad):
    # KB-grounding must be real: every [[wikilink]] in a squad description must
    # resolve to an existing vault note (by basename, like Obsidian does).
    basenames = _vault_basenames()
    for link in WIKILINK_RE.findall(squad.description):
        base = unicodedata.normalize(
            "NFC", link.split("|")[0].split("/")[-1].strip()
        )
        assert base in basenames, f"{squad.id} cites missing KB note '[[{link}]]'"
