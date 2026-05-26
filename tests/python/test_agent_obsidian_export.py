"""Tests for the agent → Obsidian export (PR86c v3.17.0)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def export_module(tmp_path, monkeypatch):
    """Isolated vault path + reloaded module per test."""
    # Patch ProfileManager.read to return a fake profile pointing at tmp_path
    from core.profile import ProfileManager

    class _FakeProfile:
        vaultPath = str(tmp_path / "vault")

    monkeypatch.setattr(
        ProfileManager, "read", lambda self: _FakeProfile(),
    )
    # Create the fake vault directory
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

    import core.agents.obsidian_export as m
    importlib.reload(m)
    return m


_SAMPLE = {
    "id": "test-agent",
    "name": "Test",
    "role": "Tester",
    "department": "dev",
    "tier": 2,
    "model": "sonnet",
    "behavioral_dna": {
        "disc": {"primary": "D", "secondary": "C"},
        "enneagram": {"type": 5, "wing": 4},
        "big_five": {"openness": 80, "conscientiousness": 70, "extraversion": 50, "agreeableness": 60, "neuroticism": 30},
        "mbti": {"type": "INTJ"},
    },
    "expertise": {
        "domains": ["pytest", "fixtures"],
        "frameworks": ["TDD"],
        "depth": "expert",
        "years_equivalent": 10,
    },
    "mental_models": {"primary": ["First Principles"], "secondary": []},
    "communication": {"tone": "Crisp", "vocabulary_level": "specialist"},
    "linked_personas": ["dhh"],
}


def test_writes_markdown_to_vault(export_module, tmp_path):
    res = export_module.export_agent_to_vault(_SAMPLE)
    assert res.path.exists()
    assert res.path.suffix == ".md"
    assert "/vault/Agents/" in str(res.path)


def test_frontmatter_contains_agent_fields(export_module):
    res = export_module.export_agent_to_vault(_SAMPLE)
    content = res.path.read_text(encoding="utf-8")
    assert "type: agent" in content
    assert "id: test-agent" in content
    assert "department: dev" in content


def test_renders_dna_section(export_module):
    res = export_module.export_agent_to_vault(_SAMPLE)
    content = res.path.read_text(encoding="utf-8")
    assert "## Behavioural DNA" in content
    assert "DISC:" in content
    assert "Enneagram:" in content
    assert "INTJ" in content
    assert "OCEAN:" in content


def test_renders_expertise_section(export_module):
    res = export_module.export_agent_to_vault(_SAMPLE)
    content = res.path.read_text(encoding="utf-8")
    assert "## Expertise" in content
    assert "pytest" in content
    assert "TDD" in content


def test_renders_linked_personas_as_wikilinks(export_module):
    res = export_module.export_agent_to_vault(_SAMPLE)
    content = res.path.read_text(encoding="utf-8")
    assert "[[dhh]]" in content


def test_refuses_missing_id(export_module):
    with pytest.raises(export_module.AgentExportError, match="id"):
        export_module.export_agent_to_vault({"name": "X"})


def test_refuses_when_vault_unconfigured(monkeypatch, tmp_path):
    """When ProfileManager has no vaultPath, export should raise."""
    from core.profile import ProfileManager

    class _NoVault:
        vaultPath = ""

    monkeypatch.setattr(ProfileManager, "read", lambda self: _NoVault())
    import core.agents.obsidian_export as m
    importlib.reload(m)
    with pytest.raises(m.AgentExportError, match="vault"):
        m.export_agent_to_vault(_SAMPLE)


def test_overwrites_existing_file(export_module):
    res1 = export_module.export_agent_to_vault(_SAMPLE)
    first = res1.path.read_text(encoding="utf-8")
    second = dict(_SAMPLE)
    second["role"] = "Different Role"
    res2 = export_module.export_agent_to_vault(second)
    assert res2.path == res1.path
    assert "Different Role" in res2.path.read_text(encoding="utf-8")


def test_yaml_str_quotes_special_chars(export_module):
    assert export_module._yaml_str("simple") == "simple"
    assert export_module._yaml_str("has: colon") == '"has: colon"'
