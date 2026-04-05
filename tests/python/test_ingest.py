"""Tests for knowledge ingest engine."""

from pathlib import Path

import pytest

from core.knowledge.ingest import IngestEngine, IngestResult, detect_source_type
from core.knowledge.vector_store import VectorStore


class TestDetectSourceType:
    def test_youtube_urls(self):
        assert detect_source_type("https://www.youtube.com/watch?v=abc123") == "youtube"
        assert detect_source_type("https://youtu.be/abc123") == "youtube"

    def test_web_urls(self):
        assert detect_source_type("https://example.com/article") == "web"
        assert detect_source_type("http://blog.com/post") == "web"

    def test_pdf(self):
        assert detect_source_type("/path/to/doc.pdf") == "pdf"
        assert detect_source_type("report.PDF") == "pdf"

    def test_audio(self):
        assert detect_source_type("recording.mp3") == "audio"
        assert detect_source_type("interview.wav") == "audio"
        assert detect_source_type("podcast.m4a") == "audio"

    def test_markdown(self):
        assert detect_source_type("notes.md") == "markdown"
        assert detect_source_type("readme.txt") == "markdown"

    def test_unknown(self):
        assert detect_source_type("binary.bin") == "unknown"


class TestIngestEngine:
    @pytest.fixture
    def store(self):
        s = VectorStore(":memory:")
        yield s
        s.close()

    @pytest.fixture
    def engine(self, store, tmp_path):
        return IngestEngine(store, media_dir=tmp_path)

    def test_ingest_markdown(self, engine, store, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Document\n\nThis is a test document with enough content to pass the minimum threshold for chunking. It contains multiple sentences and paragraphs to be properly processed by the ingest engine.\n\n## Section Two\n\nMore content here for the second section of the document.")

        progress_calls = []
        result = engine.ingest(
            str(md_file),
            source_type="markdown",
            on_progress=lambda p, m: progress_calls.append((p, m)),
        )

        assert result.success
        assert result.chunks_created > 0
        assert result.text_length > 0
        assert result.title == "test"
        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == 100  # Last call is 100%

    def test_ingest_markdown_not_found(self, engine):
        result = engine.ingest("/nonexistent/file.md", source_type="markdown")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_ingest_unknown_type(self, engine):
        result = engine.ingest("file.xyz", source_type="unknown")
        assert not result.success
        assert "Unsupported" in result.error

    def test_ingest_short_content(self, engine, tmp_path):
        short_file = tmp_path / "short.md"
        short_file.write_text("Too short")

        result = engine.ingest(str(short_file), source_type="markdown")
        assert not result.success
        assert "too short" in result.error.lower()

    def test_ingest_indexes_into_store(self, engine, store, tmp_path):
        md_file = tmp_path / "indexed.md"
        md_file.write_text("# Knowledge Article\n\nThis article contains important information about ArkaOS architecture and design patterns. It covers the agent hierarchy, workflow engine, and synapse context injection system in detail.\n\n## Architecture\n\nThe system uses a multi-tier agent hierarchy with behavioral DNA profiles.")

        result = engine.ingest(str(md_file), source_type="markdown")
        assert result.success

        stats = store.get_stats()
        assert stats["total_chunks"] > 0

    def test_ingest_web_missing_deps(self, engine, monkeypatch):
        # Simulate missing requests
        import builtins
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name in ("requests", "bs4"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = engine.ingest("https://example.com", source_type="web")
        assert not result.success

    def test_progress_callback_flow(self, engine, tmp_path):
        md_file = tmp_path / "progress.md"
        md_file.write_text("# Progress Test\n\nContent with enough words to pass the minimum threshold for the ingestion engine to process it and create meaningful chunks for indexing into the vector database.")

        progress_values = []
        engine.ingest(
            str(md_file),
            source_type="markdown",
            on_progress=lambda p, m: progress_values.append(p),
        )

        # Progress should be monotonically increasing
        assert progress_values == sorted(progress_values)
        assert progress_values[0] == 0
        assert progress_values[-1] == 100

    def test_ingest_with_metadata(self, engine, store, tmp_path):
        md_file = tmp_path / "meta.md"
        md_file.write_text("# Metadata Test\n\nThis document tests that custom metadata is properly attached to the indexed chunks when they are stored in the vector database for later retrieval.")

        result = engine.ingest(
            str(md_file),
            source_type="markdown",
            metadata={"project": "arkaos", "category": "docs"},
        )
        assert result.success


class TestIngestResult:
    def test_success_result(self):
        r = IngestResult(source="test.md", source_type="markdown", text_length=500, chunks_created=3, title="Test", success=True)
        assert r.success
        assert r.chunks_created == 3

    def test_error_result(self):
        r = IngestResult(source="bad.url", source_type="youtube", error="Download failed", success=False)
        assert not r.success
        assert r.error == "Download failed"
