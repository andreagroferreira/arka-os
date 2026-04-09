"""Tests for ObsidianWriter and VectorWriter — KnowledgeEntry dual-write."""

from pathlib import Path

import pytest

from core.cognition.memory.obsidian import CATEGORY_FOLDERS, ObsidianWriter
from core.cognition.memory.schemas import KnowledgeEntry
from core.cognition.memory.vector import VectorWriter


# --- Helpers ---

def make_entry(**overrides) -> KnowledgeEntry:
    defaults = {
        "title": "Laravel Sanctum Auth Setup",
        "category": "pattern",
        "tags": ["laravel", "auth", "sanctum"],
        "stacks": ["laravel", "php"],
        "content": "## Setup\n\nInstall Sanctum and publish config.",
        "source_project": "fovory",
        "applicable_to": "laravel",
        "confidence": 0.75,
        "times_used": 3,
    }
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


# --- Tests ---

class TestObsidianWriter:
    @pytest.fixture
    def writer(self, tmp_path: Path) -> ObsidianWriter:
        return ObsidianWriter(vault_base_path=str(tmp_path))

    @pytest.fixture
    def tmp_writer_path(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_write_creates_file(self, writer: ObsidianWriter, tmp_writer_path: Path) -> None:
        """File exists at the expected path after write."""
        path_str = writer.write(make_entry())
        assert Path(path_str).exists()

    def test_write_has_frontmatter(self, writer: ObsidianWriter) -> None:
        """Frontmatter starts with --- and contains all KnowledgeEntry fields."""
        entry = make_entry()
        path_str = writer.write(entry)
        content = Path(path_str).read_text()

        assert content.startswith("---")
        assert f"id: {entry.id}" in content
        assert f"title: {entry.title}" in content
        assert f"category: {entry.category}" in content
        assert "tags:" in content
        assert "stacks:" in content
        assert f"source_project: {entry.source_project}" in content
        assert f"applicable_to: {entry.applicable_to}" in content
        assert f"confidence: {entry.confidence}" in content
        assert f"times_used: {entry.times_used}" in content
        assert "created_at:" in content
        assert "updated_at:" in content

    def test_write_has_content_body(self, writer: ObsidianWriter) -> None:
        """Content markdown appears after the frontmatter block."""
        entry = make_entry(content="## Setup\n\nInstall Sanctum and publish config.")
        path_str = writer.write(entry)
        file_content = Path(path_str).read_text()

        # Frontmatter closes at second ---; content must follow
        parts = file_content.split("---", 2)
        assert len(parts) == 3
        body = parts[2]
        assert "## Setup" in body
        assert "Install Sanctum" in body

    def test_write_category_maps_to_folder(
        self, writer: ObsidianWriter, tmp_writer_path: Path
    ) -> None:
        """Each category writes to the correct subfolder."""
        categories_to_test = [
            "pattern",
            "anti_pattern",
            "solution",
            "architecture",
            "lesson",
            "improvement",
        ]
        for cat in categories_to_test:
            entry = make_entry(category=cat, title=f"Entry for {cat}")
            path_str = writer.write(entry)
            written = Path(path_str)
            expected_folder = CATEGORY_FOLDERS[cat]
            assert written.parent.name == expected_folder, (
                f"category '{cat}' should map to '{expected_folder}', "
                f"got '{written.parent.name}'"
            )

    def test_write_updates_existing(self, writer: ObsidianWriter) -> None:
        """Second write with same id/title overwrites the file with new data."""
        entry = make_entry(confidence=0.5)
        path_first = writer.write(entry)

        # Mutate confidence and re-write
        updated = entry.model_copy(update={"confidence": 0.99})
        path_second = writer.write(updated)

        assert path_first == path_second
        content = Path(path_second).read_text()
        assert "confidence: 0.99" in content
        assert "confidence: 0.5" not in content


# --- VectorWriter Tests ---

class TestVectorWriter:
    @pytest.fixture
    def writer(self, tmp_path: Path) -> VectorWriter:
        db = VectorWriter(db_path=str(tmp_path / "test_vector.db"))
        yield db
        db.close()

    def test_write_indexes_entry(self, writer: VectorWriter) -> None:
        """write() returns True when the entry is successfully stored."""
        entry = make_entry()
        result = writer.write(entry)
        assert result is True

    def test_search_finds_entry(self, writer: VectorWriter) -> None:
        """search() with matching keywords returns the written entry."""
        entry = make_entry(
            title="Laravel Sanctum Auth Setup",
            tags=["laravel", "auth", "sanctum"],
            content="Install Sanctum and publish the config.",
        )
        writer.write(entry)

        results = writer.search("laravel sanctum")
        assert len(results) >= 1
        titles = [r["title"] for r in results]
        assert entry.title in titles

    def test_search_returns_metadata(self, writer: VectorWriter) -> None:
        """Result dicts include entry_id, confidence, and applicable_to."""
        entry = make_entry(confidence=0.8, applicable_to="laravel")
        writer.write(entry)

        results = writer.search("laravel")
        assert len(results) >= 1
        result = results[0]
        assert "entry_id" in result
        assert "confidence" in result
        assert "applicable_to" in result
        assert result["applicable_to"] == "laravel"
        assert result["confidence"] == pytest.approx(0.8)

    def test_update_replaces_entry(self, writer: VectorWriter) -> None:
        """Writing the same entry twice upserts — no duplicates, data updated."""
        entry = make_entry(confidence=0.5)
        writer.write(entry)

        updated = entry.model_copy(update={"confidence": 0.95})
        writer.write(updated)

        results = writer.search("laravel sanctum")
        matching = [r for r in results if r["entry_id"] == entry.id]
        assert len(matching) == 1
        assert matching[0]["confidence"] == pytest.approx(0.95)


# --- DualWriter Tests ---

class TestDualWriter:
    from core.cognition.memory.writer import DualWriter

    @pytest.fixture
    def dual_writer(self, tmp_path: Path):
        from core.cognition.memory.writer import DualWriter
        obsidian_base = str(tmp_path / "vault")
        vector_db = str(tmp_path / "vector.db")
        writer = DualWriter(obsidian_base=obsidian_base, vector_db_path=vector_db)
        yield writer
        writer.close()

    def test_write_persists_to_both(self, dual_writer, tmp_path: Path) -> None:
        """write() stores to Obsidian (file exists) and Vector DB (indexed True)."""
        entry = make_entry()
        result = dual_writer.write(entry)

        assert result.obsidian_path is not None
        assert result.vector_indexed is True
        assert Path(result.obsidian_path).exists()
        assert result.obsidian_error is None
        assert result.vector_error is None

    def test_write_survives_obsidian_failure(self, tmp_path: Path) -> None:
        """If Obsidian path is invalid, vector still indexes and obsidian_error is set."""
        from core.cognition.memory.writer import DualWriter

        # Use a path that cannot be written to (root-level invalid location)
        bad_obsidian = "/no/such/directory/vault"
        vector_db = str(tmp_path / "vector_fallback.db")
        writer = DualWriter(obsidian_base=bad_obsidian, vector_db_path=vector_db)
        try:
            result = writer.write(make_entry())
        finally:
            writer.close()

        assert result.obsidian_path is None
        assert result.obsidian_error is not None
        assert result.vector_indexed is True
        assert result.vector_error is None

    def test_search_delegates_to_vector(self, dual_writer) -> None:
        """After write(), search() returns the written entry via vector store."""
        entry = make_entry(
            title="Sanctum Token Auth",
            tags=["sanctum", "token", "auth"],
            content="Use Sanctum for stateless token-based authentication.",
        )
        dual_writer.write(entry)

        results = dual_writer.search("sanctum token")
        assert len(results) >= 1
        titles = [r["title"] for r in results]
        assert entry.title in titles

    def test_write_returns_stats(self, dual_writer) -> None:
        """WriteResult exposes all 4 attributes with correct types."""
        from core.cognition.memory.writer import WriteResult

        result = dual_writer.write(make_entry())

        assert hasattr(result, "obsidian_path")
        assert hasattr(result, "obsidian_error")
        assert hasattr(result, "vector_indexed")
        assert hasattr(result, "vector_error")
        assert isinstance(result, WriteResult)
