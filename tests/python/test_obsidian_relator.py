"""Tests for Obsidian relator module."""

import shutil
from pathlib import Path

import pytest

from core.obsidian.relator import (
    RelatedNote,
    ensure_tags,
    find_related,
    generate_wikilinks_block,
    update_back_references,
    update_mocs,
)


FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "obsidian_vault"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, dest)
    return dest


class TestFindRelated:
    def test_returns_related_for_laravel_content(self, vault: Path):
        query = "Laravel service pattern with transactions and repositories"
        results = find_related(query, vault, top_n=3, min_similarity=0.01)
        assert len(results) > 0
        titles = [r.title for r in results]
        assert any("Laravel" in t or "Repository" in t for t in titles)

    def test_empty_vault_returns_empty(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert find_related("anything", empty) == []

    def test_nonexistent_vault_returns_empty(self, tmp_path: Path):
        ghost = tmp_path / "ghost"
        assert find_related("query", ghost) == []

    def test_respects_top_n(self, vault: Path):
        results = find_related("pattern laravel service repository", vault, top_n=1, min_similarity=0.0)
        assert len(results) <= 1

    def test_respects_min_similarity(self, vault: Path):
        results = find_related("quantum biology orbital", vault, min_similarity=0.9)
        assert results == []

    def test_excludes_self(self, vault: Path):
        target = vault / "🧠 Knowledge Base" / "Laravel Patterns" / "Laravel Service Pattern.md"
        results = find_related(
            "service pattern laravel", vault, min_similarity=0.0, exclude=target
        )
        for r in results:
            assert r.path.resolve() != target.resolve()

    def test_corrupt_file_does_not_crash(self, vault: Path, tmp_path: Path):
        bad = vault / "corrupt.md"
        bad.write_bytes(b"\xff\xfe\x00invalid")
        results = find_related("laravel pattern", vault, min_similarity=0.0)
        assert isinstance(results, list)


class TestWikilinksBlock:
    def test_empty_related_returns_empty_string(self):
        assert generate_wikilinks_block([]) == ""

    def test_generates_markdown_block(self, tmp_path: Path):
        related = [
            RelatedNote(path=tmp_path / "a.md", title="A", score=0.8),
            RelatedNote(path=tmp_path / "b.md", title="B", score=0.6),
        ]
        block = generate_wikilinks_block(related)
        assert "## Related" in block
        assert "[[A]]" in block
        assert "[[B]]" in block
        assert "0.80" in block


class TestBackReferences:
    def test_creates_related_block_when_absent(self, tmp_path: Path):
        note = tmp_path / "target.md"
        note.write_text("# Target\n\nbody")
        related = [RelatedNote(path=note, title="Target", score=1.0)]
        updated = update_back_references(note, related, "New Note")
        assert updated == 1
        text = note.read_text(encoding="utf-8")
        assert "## Related" in text
        assert "[[New Note]]" in text

    def test_appends_to_existing_related_block(self, tmp_path: Path):
        note = tmp_path / "target.md"
        note.write_text("# Target\n\n## Related\n\n- [[Existing]]\n")
        related = [RelatedNote(path=note, title="Target", score=1.0)]
        update_back_references(note, related, "New Note")
        text = note.read_text(encoding="utf-8")
        assert "[[Existing]]" in text
        assert "[[New Note]]" in text

    def test_idempotent_on_duplicate_link(self, tmp_path: Path):
        note = tmp_path / "target.md"
        note.write_text("# Target\n\n## Related\n\n- [[New Note]]\n")
        related = [RelatedNote(path=note, title="Target", score=1.0)]
        updated = update_back_references(note, related, "New Note")
        assert updated == 0

    def test_missing_file_skipped(self, tmp_path: Path):
        missing = tmp_path / "ghost.md"
        related = [RelatedNote(path=missing, title="Ghost", score=1.0)]
        updated = update_back_references(missing, related, "New Note")
        assert updated == 0


class TestUpdateMocs:
    def test_appends_entry_to_existing_moc(self, vault: Path):
        updated = update_mocs("New Pattern", ["Topics MOC.md"], vault)
        assert updated == 1
        moc_text = (vault / "Topics MOC.md").read_text(encoding="utf-8")
        assert "[[New Pattern]]" in moc_text

    def test_skips_missing_moc(self, vault: Path):
        updated = update_mocs("X", ["Does Not Exist MOC.md"], vault)
        assert updated == 0

    def test_idempotent_on_duplicate(self, vault: Path):
        update_mocs("Once", ["Topics MOC.md"], vault)
        second = update_mocs("Once", ["Topics MOC.md"], vault)
        assert second == 0

    def test_multiple_mocs(self, vault: Path):
        updated = update_mocs(
            "Multi", ["Topics MOC.md", "Projects MOC.md"], vault
        )
        assert updated == 2


class TestEnsureTags:
    def test_dedupe_case_insensitive(self):
        result = ensure_tags(["Arkaos", "arkaos", "dev"])
        assert len(result) == 2

    def test_strips_empties(self):
        result = ensure_tags(["", None, "x"])  # type: ignore[list-item]
        assert result == ["x"]

    def test_dedupe_against_existing(self):
        result = ensure_tags(["new", "old"], existing=["old"])
        assert result == ["new"]

    def test_preserves_order(self):
        result = ensure_tags(["b", "a", "c"])
        assert result == ["b", "a", "c"]

    def test_empty_inputs(self):
        assert ensure_tags([]) == []
