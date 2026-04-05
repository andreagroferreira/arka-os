"""Tests for persona system."""

import json
from pathlib import Path

import pytest

from core.personas.schema import Persona, PersonaDISC, PersonaEnneagram, PersonaBigFive
from core.personas.manager import PersonaManager


@pytest.fixture
def manager(tmp_path):
    return PersonaManager(storage_path=tmp_path / "personas.json")


def _sample_persona() -> Persona:
    return Persona(
        id="alex-hormozi",
        name="Alex Hormozi",
        title="Business Strategy",
        tagline="The Natural Commander",
        source="Alex Hormozi",
        disc=PersonaDISC(primary="D", secondary="I", communication_style="Direct, high-energy"),
        enneagram=PersonaEnneagram(type=3, wing=4, core_motivation="Achievement", core_fear="Failure"),
        big_five=PersonaBigFive(openness=80, conscientiousness=92, extraversion=85, agreeableness=35, neuroticism=20),
        mbti="ENTJ",
        mental_models=["Grand Slam Offer", "Value Equation", "Lead Magnets"],
        expertise_domains=["business strategy", "offer creation", "sales"],
        frameworks=["$100M Offers", "Value Equation", "Gym Launch"],
    )


class TestPersonaSchema:
    def test_create_persona(self):
        p = _sample_persona()
        assert p.id == "alex-hormozi"
        assert p.mbti == "ENTJ"
        assert p.big_five.openness == 80

    def test_to_agent_yaml(self):
        p = _sample_persona()
        agent = p.to_agent_yaml(department="strategy", tier=2)
        assert agent["id"] == "persona-alex-hormozi"
        assert agent["department"] == "strategy"
        assert agent["tier"] == 2
        assert agent["behavioral_dna"]["disc"]["primary"] == "D"
        assert agent["behavioral_dna"]["mbti"]["type"] == "ENTJ"
        assert len(agent["mental_models"]["primary"]) <= 3

    def test_default_persona(self):
        p = Persona(id="test", name="Test")
        assert p.mbti == "INTJ"
        assert p.big_five.openness == 50


class TestPersonaManager:
    def test_create(self, manager):
        p = _sample_persona()
        result = manager.create(p)
        assert result.created_at != ""
        assert manager.get("alex-hormozi") is not None

    def test_list_all(self, manager):
        manager.create(_sample_persona())
        personas = manager.list_all()
        assert len(personas) == 1

    def test_update(self, manager):
        manager.create(_sample_persona())
        updated = manager.update("alex-hormozi", {"title": "Updated Title"})
        assert updated.title == "Updated Title"

    def test_delete(self, manager):
        manager.create(_sample_persona())
        assert manager.delete("alex-hormozi")
        assert manager.get("alex-hormozi") is None
        assert not manager.delete("nonexistent")

    def test_persistence(self, tmp_path):
        path = tmp_path / "personas.json"
        m1 = PersonaManager(storage_path=path)
        m1.create(_sample_persona())

        m2 = PersonaManager(storage_path=path)
        assert m2.get("alex-hormozi") is not None
        assert m2.get("alex-hormozi").mbti == "ENTJ"

    def test_clone_to_agent(self, manager, tmp_path):
        manager.create(_sample_persona())
        agents_dir = tmp_path / "agents"

        agent_id = manager.clone_to_agent("alex-hormozi", department="strategy", agents_dir=str(agents_dir))
        assert agent_id == "persona-alex-hormozi"
        assert (agents_dir / "persona-alex-hormozi.yaml").exists()

        # Check persona tracks the clone
        p = manager.get("alex-hormozi")
        assert "persona-alex-hormozi" in p.cloned_to_agents

    def test_clone_nonexistent(self, manager):
        assert manager.clone_to_agent("nonexistent") is None

    def test_clone_yaml_content(self, manager, tmp_path):
        import yaml
        manager.create(_sample_persona())
        agents_dir = tmp_path / "agents"
        manager.clone_to_agent("alex-hormozi", department="dev", tier=1, agents_dir=str(agents_dir))

        agent_file = agents_dir / "persona-alex-hormozi.yaml"
        data = yaml.safe_load(agent_file.read_text())
        assert data["department"] == "dev"
        assert data["tier"] == 1
        assert data["behavioral_dna"]["disc"]["primary"] == "D"
