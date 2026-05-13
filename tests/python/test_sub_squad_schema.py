"""Tests for the v2.27.0 Sub-Squad pattern in the Agent schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.agents.loader import load_all_agents
from core.agents.schema import (
    Agent,
    BehavioralDNA,
    BigFiveProfile,
    DISCProfile,
    DISCType,
    EnneagramProfile,
    EnneagramType,
    MBTIProfile,
    MBTIType,
)


def _dna() -> BehavioralDNA:
    """Minimal valid behavioural DNA for schema-only tests."""
    return BehavioralDNA(
        disc=DISCProfile(primary=DISCType.D, secondary=DISCType.C, communication_style="x", under_pressure="x", motivator="x"),
        enneagram=EnneagramProfile(
            type=EnneagramType.CHALLENGER,
            wing=9,
            core_motivation="x",
            core_fear="x",
            subtype="self-preservation",
        ),
        big_five=BigFiveProfile(openness=50, conscientiousness=50, extraversion=50, agreeableness=50, neuroticism=50),
        mbti=MBTIProfile(type=MBTIType.ESTJ),
    )


def _agent(parent_squad: str | None = None, sub_squad_role: str | None = None) -> Agent:
    kwargs = {
        "id": "x-1",
        "name": "X",
        "role": "Tester",
        "department": "brand",
        "tier": 2,
        "behavioral_dna": _dna(),
    }
    if parent_squad is not None:
        kwargs["parent_squad"] = parent_squad
    if sub_squad_role is not None:
        kwargs["sub_squad_role"] = sub_squad_role
    return Agent(**kwargs)


def test_agent_without_sub_squad_fields_is_valid():
    a = _agent()
    assert a.parent_squad is None
    assert a.sub_squad_role is None


def test_agent_with_parent_squad_only_is_valid():
    a = _agent(parent_squad="brand")
    assert a.parent_squad == "brand"
    assert a.sub_squad_role is None


def test_agent_with_both_sub_squad_fields_is_valid():
    a = _agent(parent_squad="brand", sub_squad_role="lead")
    assert a.parent_squad == "brand"
    assert a.sub_squad_role == "lead"


def test_sub_squad_role_without_parent_squad_raises():
    with pytest.raises(ValidationError) as exc_info:
        _agent(sub_squad_role="lead")
    assert "parent_squad" in str(exc_info.value)


def test_design_ops_subsquad_yaml_files_load():
    """All four design-ops agents introduced in PR5 must load cleanly."""
    repo_root = Path(__file__).resolve().parents[2]
    agents = load_all_agents(repo_root / "departments")
    design_ops = [a for a in agents if a.parent_squad == "brand" and a.sub_squad_role]
    assert len(design_ops) == 4
    roles = {a.sub_squad_role for a in design_ops}
    assert roles == {"lead", "extraction-script-writer", "wcag-auditor", "shadcn-padronizer"}


def test_design_ops_lead_is_tier_one():
    repo_root = Path(__file__).resolve().parents[2]
    agents = load_all_agents(repo_root / "departments")
    lead = next(a for a in agents if a.sub_squad_role == "lead" and a.parent_squad == "brand")
    assert lead.tier == 1
    assert lead.name == "Iris"


def test_design_ops_specialists_are_tier_two():
    repo_root = Path(__file__).resolve().parents[2]
    agents = load_all_agents(repo_root / "departments")
    specialists = [
        a for a in agents
        if a.parent_squad == "brand" and a.sub_squad_role in {"extraction-script-writer", "wcag-auditor", "shadcn-padronizer"}
    ]
    assert all(a.tier == 2 for a in specialists)


def test_agent_loader_picks_up_nested_subdirectories():
    """The rglob change in PR5 must keep loading flat-directory agents too."""
    repo_root = Path(__file__).resolve().parents[2]
    agents = load_all_agents(repo_root / "departments")
    flat_brand_agents = [a for a in agents if a.department == "brand" and a.parent_squad is None]
    assert len(flat_brand_agents) >= 2  # at minimum brand-director-valentina and ux-designer
