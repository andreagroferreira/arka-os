"""Tests for knowledge system — chunker, vector store, Synapse layer."""

import pytest
from pathlib import Path

from core.knowledge.chunker import chunk_markdown, Chunk
from core.knowledge.vector_store import VectorStore
from core.knowledge.indexer import index_directory


class TestChunker:
    def test_basic_chunking(self):
        content = "# Title\n\nFirst paragraph here.\n\nSecond paragraph here."
        chunks = chunk_markdown(content)
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_strips_frontmatter(self):
        content = "---\nname: test\n---\n\n# Hello\n\nContent here."
        chunks = chunk_markdown(content)
        assert all("---" not in c.text for c in chunks)

    def test_respects_max_tokens(self):
        content = "\n\n".join([f"Paragraph {i} with some words." for i in range(50)])
        chunks = chunk_markdown(content, max_tokens=50)
        for c in chunks:
            assert c.token_estimate <= 60  # Allow some tolerance

    def test_tracks_headings(self):
        content = "# Main\n\nIntro.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        chunks = chunk_markdown(content, max_tokens=1000)
        assert any(c.heading == "Section B" for c in chunks)

    def test_preserves_source(self):
        chunks = chunk_markdown("# Test\n\nContent.", source="/path/to/file.md")
        assert all(c.source == "/path/to/file.md" for c in chunks)

    def test_empty_content(self):
        assert chunk_markdown("") == []

    def test_chunk_index(self):
        content = "\n\n".join([f"Paragraph {i}." for i in range(10)])
        chunks = chunk_markdown(content, max_tokens=20)
        for i, c in enumerate(chunks):
            assert c.index == i


class TestVectorStore:
    @pytest.fixture
    def store(self):
        s = VectorStore(":memory:")
        yield s
        s.close()

    def test_index_and_stats(self, store):
        store.index_chunks(
            texts=["Hello world", "Test document"],
            source="test.md",
            file_hash="abc123",
        )
        stats = store.get_stats()
        assert stats["total_chunks"] == 2
        assert stats["total_files"] == 1

    def test_search_returns_results(self, store):
        store.index_chunks(
            texts=[
                "Python programming tutorial",
                "JavaScript web development",
                "Database schema design",
            ],
            source="docs.md",
        )
        results = store.search("python coding", top_k=2)
        assert len(results) <= 2
        assert all("text" in r and "score" in r for r in results)

    def test_is_file_indexed(self, store):
        assert not store.is_file_indexed("hash123")
        store.index_chunks(texts=["Content"], file_hash="hash123")
        assert store.is_file_indexed("hash123")

    def test_remove_file(self, store):
        store.index_chunks(texts=["Content A"], source="a.md")
        store.index_chunks(texts=["Content B"], source="b.md")
        removed = store.remove_file("a.md")
        assert removed == 1
        assert store.get_stats()["total_chunks"] == 1

    def test_clear(self, store):
        store.index_chunks(texts=["Content"], source="test.md")
        store.clear()
        assert store.get_stats()["total_chunks"] == 0

    def test_empty_search(self, store):
        results = store.search("anything", top_k=5)
        assert results == []

    def test_search_with_headings(self, store):
        store.index_chunks(
            texts=["Security vulnerability details"],
            headings=["OWASP Top 10"],
            source="security.md",
        )
        results = store.search("vulnerability")
        assert len(results) >= 1


class TestIndexer:
    def test_index_directory(self, tmp_path):
        # Create test markdown files
        (tmp_path / "doc1.md").write_text(
            "# Doc 1\n\nFirst document content about Python programming language and its ecosystem with libraries and frameworks for web development and data science applications."
        )
        (tmp_path / "doc2.md").write_text(
            "# Doc 2\n\nSecond document about JavaScript web development including React, Vue, Angular frameworks and Node.js backend runtime with express and fastify servers."
        )
        (tmp_path / "short.md").write_text("Too short")  # Should be skipped (< 20 words)

        store = VectorStore(":memory:")
        result = index_directory(tmp_path, store)

        assert result["files_scanned"] == 3
        assert result["files_indexed"] == 2
        assert result["files_skipped"] == 1  # short.md
        assert result["chunks_created"] >= 2
        store.close()

    def test_incremental_indexing(self, tmp_path):
        (tmp_path / "doc.md").write_text(
            "# Test\n\nSome content for indexing with enough words to pass the minimum threshold of twenty words required by the indexer for processing documents."
        )

        store = VectorStore(":memory:")
        r1 = index_directory(tmp_path, store)
        r2 = index_directory(tmp_path, store)  # Second pass

        assert r1["files_indexed"] == 1
        assert r2["files_skipped"] == 1  # Already indexed
        store.close()

    def test_skip_hidden_dirs(self, tmp_path):
        hidden = tmp_path / ".obsidian"
        hidden.mkdir()
        (hidden / "config.md").write_text("# Config\n\nThis should be skipped.")
        (tmp_path / "visible.md").write_text(
            "# Visible\n\nThis should be indexed because it has enough content words to pass the minimum threshold for the indexer to consider it a valid document for chunking and embedding."
        )

        store = VectorStore(":memory:")
        result = index_directory(tmp_path, store)
        assert result["files_indexed"] == 1
        store.close()

    def test_empty_directory(self, tmp_path):
        store = VectorStore(":memory:")
        result = index_directory(tmp_path, store)
        assert result["files_scanned"] == 0
        store.close()


class TestKnowledgeRetrievalLayer:
    def test_layer_with_store(self):
        from core.synapse.layers import KnowledgeRetrievalLayer, PromptContext

        store = VectorStore(":memory:")
        store.index_chunks(
            texts=["OWASP security best practices for web applications"],
            source="security.md",
        )

        layer = KnowledgeRetrievalLayer(vector_store=store)
        assert layer.id == "L3.5"
        assert layer.priority == 35

        ctx = PromptContext(user_input="security best practices")
        result = layer.compute(ctx)
        assert result.layer_id == "L3.5"
        assert result.tag  # Should have knowledge tag
        assert "knowledge:" in result.tag  # Tag format: [knowledge:N chunks]
        store.close()

    def test_layer_without_store(self):
        from core.synapse.layers import KnowledgeRetrievalLayer, PromptContext

        layer = KnowledgeRetrievalLayer(vector_store=None)
        ctx = PromptContext(user_input="test")
        result = layer.compute(ctx)
        assert result.tag == ""  # Graceful skip

    def test_layer_empty_input(self):
        from core.synapse.layers import KnowledgeRetrievalLayer, PromptContext

        store = VectorStore(":memory:")
        layer = KnowledgeRetrievalLayer(vector_store=store)
        ctx = PromptContext(user_input="")
        result = layer.compute(ctx)
        assert result.tag == ""
        store.close()

    def test_layer_in_engine(self):
        from core.synapse.engine import create_default_engine
        from core.synapse.layers import PromptContext

        store = VectorStore(":memory:")
        store.index_chunks(texts=["ArkaOS deployment guide"], source="deploy.md")

        engine = create_default_engine(vector_store=store)
        # 10 default + L3.5 KnowledgeRetrieval + L2.5 KBContext (both gated
        # on vector_store/vault being present).
        assert engine.layer_count == 12

        ctx = PromptContext(user_input="how to deploy")
        result = engine.inject(ctx)
        # L3.5 should be in the results
        layer_ids = [lr.layer_id for lr in result.layers]
        assert "L3.5" in layer_ids
        store.close()


class TestKBSessionCache:
    """Tests for on-demand knowledge retrieval via session cache."""

    def test_store_and_retrieve(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(
            session_id="test-session-001",
            project_path="/test/project",
            cache_dir=str(tmp_path),
        )

        results = [
            {"text": "ArkaOS routing works by matching commands", "source": "routing.md"},
            {"text": "Commands are resolved via Synapse layers", "source": "synapse.md"},
        ]
        cache.store("how does routing work in ArkaOS", results)

        retrieved = cache.get_overlap("routing arkaos deployment", threshold=0.3)
        assert len(retrieved) == 2
        assert "ArkaOS routing" in retrieved[0]["text"]

    def test_jaccard_similarity(self):
        from core.synapse.kb_cache import KBSessionCache

        topics1 = {"routing", "commands", "synapse"}
        topics2 = {"routing", "setup", "configuration"}

        score = KBSessionCache.jaccard(topics1, topics2)
        assert 0.0 < score < 1.0
        assert score == 1.0 / 5.0  # 1 intersection / 5 union

    def test_jaccard_no_overlap(self):
        from core.synapse.kb_cache import KBSessionCache

        topics1 = {"python", "programming"}
        topics2 = {"cooking", "recipes"}

        score = KBSessionCache.jaccard(topics1, topics2)
        assert score == 0.0

    def test_extract_topics(self):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(session_id="test", project_path="/test")
        topics = cache.extract_topics("how to deploy arkaos on kubernetes using docker")

        assert "deploy" in topics
        assert "arkaos" in topics
        assert "kubernetes" in topics
        assert "docker" in topics
        assert "how" not in topics
        assert "to" not in topics
        assert "on" not in topics

    def test_project_scoped_cache(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache1 = KBSessionCache(
            session_id="shared-session",
            project_path="/project/a",
            cache_dir=str(tmp_path / "proj_a"),
        )
        cache2 = KBSessionCache(
            session_id="shared-session",
            project_path="/project/b",
            cache_dir=str(tmp_path / "proj_b"),
        )

        cache1.store("project A specific knowledge", [{"text": "Project A info", "source": "a.md"}])

        results_from_a = cache1.retrieve(topics={"project", "specific", "knowledge"})
        results_from_b = cache2.retrieve(topics={"project", "specific", "knowledge"})

        assert len(results_from_a) == 1
        assert len(results_from_b) == 0  # Different project, no access

    def test_auto_inject_threshold(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(
            session_id="test-threshold",
            project_path="/test",
            cache_dir=str(tmp_path),
        )

        cache.store(
            "deploy arkaos on kubernetes", [{"text": "K8s deployment guide", "source": "k8s.md"}]
        )

        strong_overlap = cache.retrieve(topics={"deploy", "kubernetes"}, threshold=0.3)
        assert len(strong_overlap) == 1

        weak_overlap = cache.retrieve(topics={"docker", "container"}, threshold=0.3)
        assert len(weak_overlap) == 0

    def test_session_cache_ttl(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache
        import time

        cache = KBSessionCache(
            session_id="test-ttl",
            project_path="/test",
            cache_dir=str(tmp_path),
            ttl_seconds=1,
        )

        cache.store("temporary knowledge", [{"text": "Will expire soon", "source": "temp.md"}])

        time.sleep(1.1)

        results = cache.retrieve(topics={"temporary", "knowledge"})
        assert len(results) == 0

    def test_get_overlap_convenience(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(
            session_id="test-overlap",
            project_path="/test",
            cache_dir=str(tmp_path),
        )

        cache.store(
            "configure arkaos settings", [{"text": "Settings configuration", "source": "config.md"}]
        )

        results = cache.get_overlap("how do I configure settings in arkaos", threshold=0.3)
        assert len(results) == 1

    def test_clear_cache(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(
            session_id="test-clear",
            project_path="/test",
            cache_dir=str(tmp_path),
        )

        cache.store("knowledge to clear", [{"text": "Will be cleared", "source": "clear.md"}])
        cache.clear()

        stats = cache.stats()
        assert stats["valid_entries"] == 0

    def test_stats(self, tmp_path):
        from core.synapse.kb_cache import KBSessionCache

        cache = KBSessionCache(
            session_id="test-stats",
            project_path="/test/project",
            cache_dir=str(tmp_path),
        )

        cache.store("first query", [{"text": "First", "source": "f.md"}])
        cache.store("second query", [{"text": "Second", "source": "s.md"}])

        stats = cache.stats()
        assert stats["session_id"] == "test-stats"
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert str(tmp_path) in stats["cache_dir"]
