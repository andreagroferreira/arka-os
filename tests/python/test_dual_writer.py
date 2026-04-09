"""Tests for ObsidianWriter — KnowledgeEntry → Obsidian markdown notes."""

from pathlib import Path

import pytest

from core.cognition.memory.obsidian import CATEGORY_FOLDERS, ObsidianWriter
from core.cognition.memory.schemas import KnowledgeEntry


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
