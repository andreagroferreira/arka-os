"""Tests for Obsidian-backed persona store (PR73 v2.91.0)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from core.personas.obsidian_store import ObsidianPersonaStore
from core.personas.schema import (
    Persona, PersonaBigFive, PersonaCommunication, PersonaDISC, PersonaEnneagram,
)


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """Create a fake vault with a Personas folder."""
    (tmp_path / "Personas").mkdir()
    return tmp_path


# ─── Read path ──────────────────────────────────────────────────────────


class TestRead:
    def test_returns_empty_when_vault_missing(self, tmp_path):
        store = ObsidianPersonaStore(vault_path=tmp_path / "no-such-vault")
        assert store.list_all() == []

    def test_returns_empty_when_personas_dir_missing(self, tmp_path):
        store = ObsidianPersonaStore(vault_path=tmp_path)
        # Personas dir doesn't exist
        assert store.list_all() == []

    def test_parses_minimal_frontmatter(self, vault_path):
        (vault_path / "Personas" / "Alex Hormozi.md").write_text(textwrap.dedent("""
            ---
            type: persona
            name: Alex Hormozi
            mbti: ENTJ
            ---

            Body content.
        """).strip())
        store = ObsidianPersonaStore(vault_path=vault_path)
        personas = store.list_all()
        assert len(personas) == 1
        assert personas[0].name == "Alex Hormozi"
        assert personas[0].mbti == "ENTJ"

    def test_parses_full_frontmatter(self, vault_path):
        fm = {
            "type": "persona",
            "name": "Naval Ravikant",
            "title": "Philosopher-Investor",
            "tagline": "Wealth without permission",
            "mbti": "INTJ",
            "disc": {"primary": "D", "secondary": "C"},
            "enneagram": {"type": 5, "wing": 4},
            "big_five": {"openness": 95, "conscientiousness": 80, "extraversion": 40, "agreeableness": 60, "neuroticism": 20},
            "mental_models": ["specific knowledge", "leverage"],
            "expertise_domains": ["startups", "investing"],
            "frameworks": ["how to get rich"],
        }
        (vault_path / "Personas" / "Naval.md").write_text(
            "---\n" + yaml.safe_dump(fm) + "---\n\nbody\n"
        )
        store = ObsidianPersonaStore(vault_path=vault_path)
        personas = store.list_all()
        assert len(personas) == 1
        p = personas[0]
        assert p.name == "Naval Ravikant"
        assert p.title == "Philosopher-Investor"
        assert p.disc.primary == "D"
        assert p.enneagram.type == 5
        assert p.big_five.openness == 95
        assert "specific knowledge" in p.mental_models
        assert "investing" in p.expertise_domains

    def test_skips_non_persona_type_files(self, vault_path):
        """MOC files / other note types in the Personas folder are ignored."""
        (vault_path / "Personas" / "Personas MOC.md").write_text(
            "---\ntype: moc\n---\n\nList of personas.\n"
        )
        (vault_path / "Personas" / "Alex.md").write_text(
            "---\ntype: persona\nname: Alex\n---\n\nbody\n"
        )
        store = ObsidianPersonaStore(vault_path=vault_path)
        personas = store.list_all()
        assert len(personas) == 1
        assert personas[0].name == "Alex"

    def test_skips_files_without_frontmatter(self, vault_path):
        (vault_path / "Personas" / "plain.md").write_text("Just a note, no fm.\n")
        store = ObsidianPersonaStore(vault_path=vault_path)
        assert store.list_all() == []

    def test_handles_legacy_expertise_alias(self, vault_path):
        """Older files used `expertise:` instead of `expertise_domains:`."""
        (vault_path / "Personas" / "Legacy.md").write_text(textwrap.dedent("""
            ---
            type: persona
            name: Legacy
            expertise:
              - x
              - y
            ---
            body
        """).strip())
        store = ObsidianPersonaStore(vault_path=vault_path)
        personas = store.list_all()
        assert personas[0].expertise_domains == ["x", "y"]

    def test_handles_corrupt_yaml(self, vault_path):
        (vault_path / "Personas" / "broken.md").write_text(
            "---\n  : missing key\n---\n\nbody\n"
        )
        # Must not raise
        store = ObsidianPersonaStore(vault_path=vault_path)
        assert store.list_all() == []


# ─── Write path ─────────────────────────────────────────────────────────


def _make_persona() -> Persona:
    return Persona(
        id="test-user",
        name="Test User",
        title="Test Title",
        tagline="A tagline",
        source="Test User",
        mbti="ENTJ",
        disc=PersonaDISC(primary="D", secondary="I"),
        enneagram=PersonaEnneagram(type=8, wing=7),
        big_five=PersonaBigFive(
            openness=80, conscientiousness=90, extraversion=70,
            agreeableness=55, neuroticism=25,
        ),
        mental_models=["first principles", "skin in the game"],
        expertise_domains=["business", "operations"],
        frameworks=["value equation"],
        key_quotes=["one job: keep providing value."],
        communication=PersonaCommunication(tone="direct", vocabulary_level="specialist"),
    )


class TestWrite:
    def test_writes_to_personas_folder(self, vault_path):
        store = ObsidianPersonaStore(vault_path=vault_path)
        path = store.write(_make_persona())
        assert path is not None
        assert path.exists()
        assert path.name == "Test User.md"

    def test_creates_personas_folder_when_missing(self, tmp_path):
        # Vault exists but Personas folder doesn't yet
        store = ObsidianPersonaStore(vault_path=tmp_path)
        path = store.write(_make_persona())
        assert path is not None
        assert (tmp_path / "Personas").exists()

    def test_returns_none_when_no_vault(self):
        store = ObsidianPersonaStore(vault_path=None)
        assert store.write(_make_persona()) is None

    def test_overwrites_existing_file(self, vault_path):
        store = ObsidianPersonaStore(vault_path=vault_path)
        p1 = _make_persona()
        path1 = store.write(p1)
        original_size = path1.stat().st_size if path1 else 0
        p2 = _make_persona()
        p2.mental_models = ["different", "models"]
        path2 = store.write(p2)
        assert path1 == path2
        new_size = path2.stat().st_size if path2 else 0
        assert new_size != original_size  # content changed

    def test_round_trip_through_list_all(self, vault_path):
        store = ObsidianPersonaStore(vault_path=vault_path)
        original = _make_persona()
        store.write(original)
        loaded = store.list_all()
        assert len(loaded) == 1
        assert loaded[0].name == original.name
        assert loaded[0].mbti == original.mbti
        assert loaded[0].disc.primary == original.disc.primary
        assert set(loaded[0].mental_models) == set(original.mental_models)

    def test_bio_md_round_trips(self, vault_path):
        """v3.70.10 — long-form bio_md must survive write -> read.

        Regression for the bug where Obsidian-source personas silently
        dropped operator edits to the MD bio (the store never serialized
        the field). Uses multi-line Markdown to exercise YAML block scalars.
        """
        store = ObsidianPersonaStore(vault_path=vault_path)
        original = _make_persona()
        original.bio_md = (
            "# Test User\n\n"
            "A multi-paragraph bio.\n\n"
            "- bullet one\n"
            "- bullet two\n\n"
            "> A quote with special chars: é, ç, \"quotes\" & ampersands.\n"
        )
        store.write(original)
        loaded = store.list_all()
        assert len(loaded) == 1
        assert loaded[0].bio_md == original.bio_md

    def test_bio_md_absent_when_empty(self, vault_path):
        """Personas without a bio must not emit a noisy `bio_md:` key."""
        store = ObsidianPersonaStore(vault_path=vault_path)
        path = store.write(_make_persona())
        assert path is not None
        assert "bio_md" not in path.read_text(encoding="utf-8")


# ─── available property ─────────────────────────────────────────────────


class TestAvailability:
    def test_available_when_personas_dir_exists(self, vault_path):
        store = ObsidianPersonaStore(vault_path=vault_path)
        assert store.available is True

    def test_not_available_when_vault_path_none(self):
        store = ObsidianPersonaStore(vault_path=None)
        assert store.available is False

    def test_not_available_when_personas_dir_missing(self, tmp_path):
        store = ObsidianPersonaStore(vault_path=tmp_path)
        assert store.available is False
