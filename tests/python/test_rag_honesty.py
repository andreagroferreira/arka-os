"""Tests for RAG honesty + grounding quarantine (PR-3 v4.1).

Covers:
- vector_store keyword fallback: score None + retrieval "keyword-degraded"
  (no more fake 0.5 similarity), one-time stderr warning, stats mode
- keyword fallback placeholder/param parity for >5-word queries
- embedder model resolution (env > config > default) and derived dims
- vec0 dimension parsing + stored-dimension guard helpers
- L2.5 degraded tag `[kb-context:N degraded=keyword]` + labeled block
- L3.5 degraded tag `[knowledge:N chunks degraded=keyword]`
- Dreaming frontmatter `grounding: inferred`
- L2.5 inferred-note quarantine (excluded by default; suffixed when
  fewer than 2 grounded notes matched)
- synapse-bridge tag regexes tolerate the degraded suffix
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import core.knowledge.embedder as embedder
import core.knowledge.vector_store as vector_store_mod
from core.cognition.dreaming import Insight, _render_markdown
from core.knowledge.vector_store import VectorStore, _parse_vec_dims
from core.synapse.layers import (
    KBContextLayer,
    KnowledgeRetrievalLayer,
    PromptContext,
    _apply_grounding_policy,
    _format_kb_block,
    _frontmatter_marks_inferred,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Fake HOME + fresh embedder/degradation state for every test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ARKA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("ARKA_BYPASS_L25", raising=False)
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-query"))
    monkeypatch.setattr(vector_store_mod, "_DEGRADED_WARNED", False)
    embedder.reset_model_cache()
    yield home
    embedder.reset_model_cache()


def _keyword_only_store(monkeypatch) -> VectorStore:
    """In-memory store forced onto the keyword-degraded path."""
    monkeypatch.setattr(vector_store_mod, "embed", lambda text: None)
    monkeypatch.setattr(vector_store_mod, "embed_batch", lambda texts: None)
    store = VectorStore(":memory:")
    store._vec_available = False
    store.index_chunks(
        texts=["Laravel service pattern guide", "Nuxt composables overview"],
        source="guide.md",
    )
    return store


class _DegradedFakeStore:
    """Vector-store stand-in returning labeled keyword-degraded hits."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query, top_k=5):  # noqa: ARG002
        return list(self._hits)[:top_k]


def _degraded_hit(text: str, source: str, metadata: dict | None = None) -> dict:
    return {
        "text": text,
        "heading": "",
        "source": source,
        "score": None,
        "retrieval": "keyword-degraded",
        "metadata": metadata or {},
    }


def _semantic_hit(text: str, source: str, score: float = 0.9,
                  metadata: dict | None = None) -> dict:
    return {
        "text": text,
        "heading": "",
        "source": source,
        "score": score,
        "retrieval": "semantic",
        "metadata": metadata or {},
    }


# --- vector_store: honest keyword fallback -----------------------------------


class TestKeywordDegradedFallback:
    def test_score_is_none_and_retrieval_labeled(self, monkeypatch):
        store = _keyword_only_store(monkeypatch)
        results = store.search("laravel service")
        assert results, "keyword fallback must still return matches"
        for r in results:
            assert r["score"] is None, "no fake similarity score"
            assert r["retrieval"] == "keyword-degraded"

    def test_one_time_stderr_warning(self, monkeypatch, capsys):
        store = _keyword_only_store(monkeypatch)
        store.search("laravel")
        store.search("laravel")  # second search must not repeat the warning
        err = capsys.readouterr().err
        assert err.count("[arka:kb-degraded]") == 1
        assert "keyword matches" in err

    def test_stats_expose_retrieval_mode(self, monkeypatch):
        store = _keyword_only_store(monkeypatch)
        stats = store.get_stats()
        assert stats["retrieval_mode"] == "keyword-degraded"

    def test_long_query_does_not_crash_placeholder_parity(self, monkeypatch):
        store = _keyword_only_store(monkeypatch)
        results = store.search("laravel service pattern guide with many extra words")
        assert isinstance(results, list)


# --- embedder: configurable model + derived dims ------------------------------


class TestEmbedderModelResolution:
    def test_default_model(self):
        assert embedder.get_model_name() == "BAAI/bge-small-en-v1.5"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("ARKA_EMBED_MODEL", "intfloat/multilingual-e5-large")
        assert embedder.get_model_name() == "intfloat/multilingual-e5-large"

    def test_config_override(self, _isolated_env):
        arkaos = _isolated_env / ".arkaos"
        arkaos.mkdir()
        (arkaos / "config.json").write_text(
            json.dumps({"knowledge": {"embedModel": embedder.RECOMMENDED_MULTILINGUAL_MODEL}}),
            encoding="utf-8",
        )
        assert embedder.get_model_name() == embedder.RECOMMENDED_MULTILINGUAL_MODEL

    def test_env_beats_config(self, _isolated_env, monkeypatch):
        arkaos = _isolated_env / ".arkaos"
        arkaos.mkdir()
        (arkaos / "config.json").write_text(
            json.dumps({"knowledge": {"embedModel": "config-model"}}), encoding="utf-8"
        )
        monkeypatch.setenv("ARKA_EMBED_MODEL", "env-model")
        assert embedder.get_model_name() == "env-model"

    def test_dims_derived_from_model(self, monkeypatch):
        assert embedder.embedding_dims("BAAI/bge-small-en-v1.5") == 384
        assert embedder.embedding_dims(embedder.RECOMMENDED_MULTILINGUAL_MODEL) == 384
        assert embedder.embedding_dims("intfloat/multilingual-e5-large") == 1024

    def test_dims_follow_configured_model(self, monkeypatch):
        monkeypatch.setenv("ARKA_EMBED_MODEL", "intfloat/multilingual-e5-large")
        embedder.reset_model_cache()
        assert embedder.embedding_dims() == 1024

    def test_legacy_constant_kept_for_backward_compat(self):
        assert embedder.EMBEDDING_DIMS == 384


class TestVecDimensionGuard:
    def test_parse_vec_dims(self):
        sql = "CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[384])"
        assert _parse_vec_dims(sql) == 384
        assert _parse_vec_dims(None) is None
        assert _parse_vec_dims("CREATE TABLE x (y TEXT)") is None

    def test_store_dims_track_configured_model(self, monkeypatch):
        monkeypatch.setattr(vector_store_mod, "embed", lambda text: None)
        monkeypatch.setattr(vector_store_mod, "embed_batch", lambda texts: None)
        monkeypatch.setenv("ARKA_EMBED_MODEL", "intfloat/multilingual-e5-large")
        embedder.reset_model_cache()
        store = VectorStore(":memory:")
        assert store._vec_dims == 1024

    def test_stored_dimension_wins_over_config(self, tmp_path, monkeypatch):
        """A pre-existing 384-dim index must survive a model switch."""
        pytest.importorskip("sqlite_vec")
        monkeypatch.setattr(vector_store_mod, "embed", lambda text: None)
        monkeypatch.setattr(vector_store_mod, "embed_batch", lambda texts: None)
        db = tmp_path / "knowledge.db"

        first = VectorStore(db)
        if not first._vec_available:
            pytest.skip("sqlite-vec extension not loadable in this env")
        assert first._vec_dims == 384
        first.close()

        monkeypatch.setenv("ARKA_EMBED_MODEL", "intfloat/multilingual-e5-large")
        embedder.reset_model_cache()
        second = VectorStore(db)
        assert second._vec_dims == 384, "stored index dimension must win"
        second.close()


# --- L2.5 / L3.5: degraded labeling -------------------------------------------


class TestDegradedLayerLabels:
    def test_l25_tag_carries_degraded_marker(self):
        layer = KBContextLayer(
            vector_store=_DegradedFakeStore([_degraded_hit("laravel notes", "/kb/a.md")])
        )
        result = layer.compute(PromptContext(user_input="laravel service"))
        assert result.tag == "[kb-context:1 degraded=keyword]"
        assert "palavras-chave" in result.content
        assert "NÃO é similaridade semântica" in result.content

    def test_l25_semantic_tag_unchanged(self):
        layer = KBContextLayer(
            vector_store=_DegradedFakeStore([_semantic_hit("laravel notes", "/kb/a.md")])
        )
        result = layer.compute(PromptContext(user_input="laravel service"))
        assert result.tag == "[kb-context:1]"
        assert "palavras-chave" not in result.content

    def test_l35_tag_carries_degraded_marker(self):
        layer = KnowledgeRetrievalLayer(
            vector_store=_DegradedFakeStore([_degraded_hit("laravel notes", "/kb/a.md")])
        )
        result = layer.compute(
            PromptContext(user_input="laravel service", extra={"session_id": "s-x"})
        )
        # Count varies with the session-cache overlap echo — the honesty
        # marker is what matters here.
        assert result.tag.startswith("[knowledge:")
        assert result.tag.endswith(" chunks degraded=keyword]")

    def test_l35_semantic_tag_unchanged(self):
        layer = KnowledgeRetrievalLayer(
            vector_store=_DegradedFakeStore([_semantic_hit("laravel notes", "/kb/a.md")])
        )
        result = layer.compute(
            PromptContext(user_input="laravel service", extra={"session_id": "s-y"})
        )
        assert result.tag.startswith("[knowledge:")
        assert result.tag.endswith(" chunks]")
        assert "degraded" not in result.tag

    def test_bridge_regexes_tolerate_degraded_suffix(self):
        spec = importlib.util.spec_from_file_location(
            "synapse_bridge", REPO_ROOT / "scripts" / "synapse-bridge.py"
        )
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        m = bridge._KB_CONTEXT_TAG_RE.search("[kb-context:3 degraded=keyword]")
        assert m and m.group(1) == "3"
        m = bridge._KNOWLEDGE_TAG_RE.search("[knowledge:2 chunks degraded=keyword]")
        assert m and m.group(1) == "2"


# --- Dreaming quarantine -------------------------------------------------------


class TestDreamingGroundingQuarantine:
    def _insight(self) -> Insight:
        return Insight(
            title="Test Insight",
            body="Something noticed.",
            confidence="medium",
            sources=["note-a.md"],
            tags=["testing"],
        )

    def test_frontmatter_marks_grounding_inferred(self):
        fm = self._insight().to_frontmatter("2026-07-04")
        assert fm["grounding"] == "inferred"

    def test_rendered_note_carries_marker_and_l25_detects_it(self):
        rendered = _render_markdown(
            self._insight().to_frontmatter("2026-07-04"), self._insight()
        )
        assert "grounding: inferred" in rendered
        assert _frontmatter_marks_inferred(rendered) is True

    def test_regular_note_not_marked(self):
        raw = "---\ntype: note\n---\n\n# Regular\n\nGrounded content."
        assert _frontmatter_marks_inferred(raw) is False

    def test_body_mention_does_not_trigger_marker(self):
        raw = "# No frontmatter\n\ngrounding: inferred appears in the body only."
        assert _frontmatter_marks_inferred(raw) is False


class TestInferredQuarantinePolicy:
    def test_excluded_when_two_grounded_notes(self):
        notes = [
            {"title": "A", "inferred": False},
            {"title": "B", "inferred": False},
            {"title": "Dream", "inferred": True},
        ]
        picked = _apply_grounding_policy(notes, max_notes=5)
        assert [n["title"] for n in picked] == ["A", "B"]

    def test_included_with_marker_when_grounded_scarce(self):
        notes = [
            {"title": "A", "inferred": False},
            {"title": "Dream", "inferred": True},
        ]
        picked = _apply_grounding_policy(notes, max_notes=5)
        assert [n["title"] for n in picked] == ["A", "Dream"]

    def test_formatter_suffixes_inferred_notes(self):
        block = _format_kb_block([
            {"title": "Dream", "path": "/kb/d.md", "excerpt": "", "relates": [],
             "inferred": True},
        ])
        assert "[[Dream]] (inferred — not authoritative)" in block

    def test_l25_end_to_end_quarantines_inferred_hits(self, tmp_path):
        inferred_note = tmp_path / "dream.md"
        inferred_note.write_text(
            "---\ntype: arkaos-insight\ngrounding: inferred\n---\n\n# Dream\n\nBody.",
            encoding="utf-8",
        )
        grounded = [
            _semantic_hit("laravel grounded one", "/kb/a.md"),
            _semantic_hit("laravel grounded two", "/kb/b.md"),
        ]
        dreamed = _semantic_hit("laravel dreamed", str(inferred_note))
        layer = KBContextLayer(
            vector_store=_DegradedFakeStore(grounded + [dreamed])
        )
        result = layer.compute(PromptContext(user_input="laravel"))
        assert result.tag == "[kb-context:2]"
        assert "dream.md" not in result.content

    def test_l25_labels_inferred_hit_when_grounded_scarce(self, tmp_path):
        inferred_note = tmp_path / "dream.md"
        inferred_note.write_text(
            "---\ngrounding: inferred\n---\n\n# Dream\n\nBody.", encoding="utf-8"
        )
        hits = [
            _semantic_hit("laravel grounded one", "/kb/a.md"),
            _semantic_hit("laravel dreamed", str(inferred_note)),
        ]
        layer = KBContextLayer(vector_store=_DegradedFakeStore(hits))
        result = layer.compute(PromptContext(user_input="laravel"))
        assert result.tag == "[kb-context:2]"
        assert "(inferred — not authoritative)" in result.content
