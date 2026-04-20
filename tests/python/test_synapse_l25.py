"""Tests for Synapse L2.5 — KB context injection.

Covers:
- Vector-store path (mocked) with similarity threshold
- Jaccard fallback when vector store is empty / missing
- Block formatting: title, path, excerpt, wikilinks
- record_obsidian_query side-effect
- Feature flag + env bypass
- Engine sequencing (L2 < L2.5 < L3)
- Long-prompt graceful handling
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from core.synapse import kb_cache
from core.synapse.engine import SynapseEngine, create_default_engine
from core.synapse.layers import (
    AgentLayer,
    DepartmentLayer,
    KBContextLayer,
    ProjectLayer,
    PromptContext,
    _extract_excerpt,
    _extract_wikilinks,
    _format_kb_block,
    _jaccard,
    _tokenize_for_jaccard,
)


FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "synapse_vault"


# --- Helpers ----------------------------------------------------------------


class _FakeStore:
    """Minimal vector store stand-in used by L2.5 tests."""

    def __init__(self, hits: list[dict] | None = None, *, raises: bool = False) -> None:
        self._hits = hits or []
        self._raises = raises

    def search(self, query: str, top_k: int = 5) -> list[dict]:  # noqa: ARG002
        if self._raises:
            raise RuntimeError("embedder unavailable")
        return list(self._hits)[:top_k]


@pytest.fixture(autouse=True)
def _isolate_marker_dir(tmp_path, monkeypatch):
    """Isolate the turn-scoped marker so tests never touch /tmp/arkaos-kb-query."""
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-query"))
    yield


@pytest.fixture(autouse=True)
def _clear_feature_flag_env(monkeypatch):
    monkeypatch.delenv("ARKA_BYPASS_L25", raising=False)
    yield


@pytest.fixture
def session_ctx():
    return PromptContext(
        user_input="como funciona o synapse L2.5 e kb architecture",
        cwd="/tmp/test",
        git_branch="feature/intelligence-v2",
        extra={"session_id": "test-session-001"},
    )


@pytest.fixture
def fixture_vault_path() -> str:
    return str(FIXTURE_VAULT)


# --- Core layer behaviour ---------------------------------------------------


def test_l25_empty_vault_returns_none():
    layer = KBContextLayer(vector_store=None, vault_path=None)
    assert layer.build("anything") is None


def test_l25_low_similarity_returns_none():
    hits = [
        {"source": "/vault/a.md", "heading": "Alpha", "text": "# Alpha\n\nNothing.", "score": 0.1},
        {"source": "/vault/b.md", "heading": "Beta", "text": "# Beta\n\nNothing.", "score": 0.2},
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    assert layer.build("unrelated query") is None


def test_l25_high_similarity_formats_block_correctly():
    hits = [
        {
            "source": "/vault/KB Architecture.md",
            "heading": "KB Architecture",
            "text": (
                "---\ntags:\n  - synapse\n---\n# KB Architecture\n\n"
                "Synapse L2.5 injects Obsidian KB context.\n"
                "Relates: [[Vector Store]], [[Embedder Setup]]."
            ),
            "score": 0.92,
        }
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("synapse L2.5 and KB architecture")
    assert block is not None
    assert block.startswith("[arka:kb-context]")
    assert "[[KB Architecture]]" in block
    assert "/vault/KB Architecture.md" in block
    assert "Vector Store" in block
    assert "Embedder Setup" in block
    assert "Consulta-as antes de ir a Context7/Web" in block


def test_l25_respects_max_notes():
    hits = [
        {
            "source": f"/vault/n{i}.md",
            "heading": f"Note {i}",
            "text": f"# Note {i}\n\nBody about synapse.",
            "score": 0.8,
        }
        for i in range(10)
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), max_notes=3, min_similarity=0.5)
    block = layer.build("synapse")
    assert block is not None
    titles = [line for line in block.splitlines() if line.startswith("- [[")]
    assert len(titles) == 3


def test_l25_extracts_wikilinks_from_body():
    raw = "# Title\n\nBody with [[Link One]] and [[Link Two|alias]] and [[Link Three]] and [[Link Four]]."
    links = _extract_wikilinks(raw, limit=3)
    assert links == ["Link One", "Link Two", "Link Three"]


def test_l25_excerpt_is_first_two_body_lines():
    raw = "---\ntags: [x]\n---\n# Title\n\nFirst body line.\nSecond body line.\nThird body line."
    excerpt = _extract_excerpt(raw, max_lines=2)
    assert "First body line." in excerpt
    assert "Second body line." in excerpt
    assert "Third body line." not in excerpt


def test_l25_fallback_to_jaccard_when_embedder_fails(fixture_vault_path):
    store = _FakeStore(raises=True)
    layer = KBContextLayer(
        vector_store=store, vault_path=fixture_vault_path, min_similarity=0.05
    )
    block = layer.build("synapse layers architecture")
    assert block is not None
    assert "[arka:kb-context]" in block
    assert "[[Synapse Layers]]" in block or "[[KB Architecture]]" in block


def test_l25_records_obsidian_query_on_call(session_ctx, fixture_vault_path):
    layer = KBContextLayer(
        vector_store=None, vault_path=fixture_vault_path, min_similarity=0.05
    )
    result = layer.compute(session_ctx)
    assert result.content  # something injected
    record = kb_cache.read_obsidian_query(session_ctx.extra["session_id"])
    assert record is not None
    assert record["last_hit_count"] >= 1
    assert record["queries"][-1]["query"] == session_ctx.user_input


def test_l25_records_query_even_when_zero_hits(session_ctx):
    layer = KBContextLayer(vector_store=_FakeStore([]), vault_path=None)
    result = layer.compute(session_ctx)
    assert result.content == ""
    record = kb_cache.read_obsidian_query(session_ctx.extra["session_id"])
    assert record is not None
    assert record["last_hit_count"] == 0


def test_l25_feature_flag_off_skips_injection(monkeypatch, fixture_vault_path, session_ctx):
    monkeypatch.setenv("ARKA_BYPASS_L25", "1")
    layer = KBContextLayer(vector_store=None, vault_path=fixture_vault_path)
    assert layer.build("synapse layers") is None
    result = layer.compute(session_ctx)
    assert result.content == ""
    # No query recorded because layer returned early
    assert kb_cache.read_obsidian_query(session_ctx.extra["session_id"]) is None


def test_l25_feature_flag_false_in_config(monkeypatch, tmp_path, fixture_vault_path):
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(json.dumps({"synapse": {"l25KbContext": False}}))
    monkeypatch.setattr(
        "core.synapse.layers._KB_CONFIG_PATH", cfg_dir / "config.json"
    )
    layer = KBContextLayer(vector_store=None, vault_path=fixture_vault_path)
    assert layer.build("synapse layers") is None


def test_l25_long_prompt_graceful(fixture_vault_path):
    long_prompt = "synapse layers " * 500  # ~7000 chars
    layer = KBContextLayer(
        vector_store=None, vault_path=fixture_vault_path, min_similarity=0.01
    )
    # Must not raise
    block = layer.build(long_prompt)
    # Either returns a block or None; never raises.
    assert block is None or block.startswith("[arka:kb-context]")


def test_l25_ignores_hits_below_similarity_floor():
    hits = [
        {"source": "/a.md", "heading": "A", "text": "# A\n\nbody", "score": 0.95},
        {"source": "/b.md", "heading": "B", "text": "# B\n\nbody", "score": 0.30},
        {"source": "/c.md", "heading": "C", "text": "# C\n\nbody", "score": 0.80},
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("query")
    assert block is not None
    assert "[[A]]" in block
    assert "[[C]]" in block
    assert "[[B]]" not in block


def test_l25_block_contains_pt_pt_phrasing():
    hits = [
        {
            "source": "/a.md",
            "heading": "A",
            "text": "# A\n\nBody text line.",
            "score": 0.9,
        }
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("q")
    assert "O teu cérebro (Obsidian)" in block
    assert "Consulta-as antes de ir a Context7/Web" in block


def test_l25_empty_prompt_returns_none():
    layer = KBContextLayer(vector_store=_FakeStore([{"score": 0.9}]), min_similarity=0.5)
    assert layer.build("") is None


# --- Engine sequencing ------------------------------------------------------


def test_engine_sequences_l25_between_l2_l3():
    engine = create_default_engine(
        vector_store=_FakeStore([]),  # enables L2.5 registration
    )
    ids = [layer.id for layer in sorted(engine._layers, key=lambda l: l.priority)]
    assert "L2" in ids
    assert "L2.5" in ids
    assert "L3" in ids
    assert ids.index("L2") < ids.index("L2.5") < ids.index("L3")


def test_engine_skips_l25_when_no_store_and_no_vault():
    engine = create_default_engine()
    ids = [layer.id for layer in engine._layers]
    assert "L2.5" not in ids


def test_engine_registers_l25_with_vault_only(fixture_vault_path):
    engine = create_default_engine(kb_vault_path=fixture_vault_path)
    ids = [layer.id for layer in engine._layers]
    assert "L2.5" in ids


# --- Pure helpers -----------------------------------------------------------


def test_jaccard_zero_for_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_one_for_identical_sets():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_tokenize_for_jaccard_drops_stopwords():
    tokens = _tokenize_for_jaccard("The quick brown fox and the lazy dog")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens


def test_format_kb_block_handles_single_note():
    notes = [{"title": "N", "path": "/p.md", "excerpt": "E", "relates": []}]
    block = _format_kb_block(notes)
    assert "1 nota relevante" in block
    assert "[[N]]" in block


def test_format_kb_block_handles_multiple_notes():
    notes = [
        {"title": "A", "path": "/a.md", "excerpt": "e", "relates": ["B"]},
        {"title": "B", "path": "/b.md", "excerpt": "e", "relates": []},
    ]
    block = _format_kb_block(notes)
    assert "2 notas relevantes" in block
    assert "[[A]]" in block and "[[B]]" in block


def test_load_fallback_notes_respects_cap(tmp_path, monkeypatch):
    """Large vaults must not blow the fallback loader: cap at 2000 notes."""
    from core.synapse import layers

    # Temporarily lower the cap to a manageable number for this test —
    # the behaviour under test is the break-on-cap, not the exact value.
    monkeypatch.setattr(layers, "_MAX_FALLBACK_NOTES", 10)

    for i in range(25):
        (tmp_path / f"note-{i:03d}.md").write_text(
            f"# Note {i}\n\nBody {i}.", encoding="utf-8"
        )

    notes = layers._load_fallback_notes(tmp_path)
    assert len(notes) == 10, (
        "loader must stop at _MAX_FALLBACK_NOTES — got "
        f"{len(notes)} notes from 25 files"
    )
