"""Tests for doctrine classification and second-pass retrieval.

Covers the three halves of the feature:
  1. index-time classification ladder + domain vocabulary
     (core/knowledge/doctrine.py + indexer metadata)
  2. derived-query construction (morphological matching, PT aliases,
     the anti-patterns that were proven harmful in live replay)
  3. the L2.5 injection path and the research-gate vault resolution
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from core.knowledge import doctrine

REPO_ROOT = Path(__file__).resolve().parents[2]

# ─── classification ladder ───────────────────────────────────────────────


class TestResolveKnowledgeClass:
    def test_explicit_frontmatter_wins_everywhere(self):
        fm = {"knowledge_class": "doctrine"}
        path = PurePosixPath("Projects/Acme/Sources/Videos/talk.md")
        assert doctrine.resolve_knowledge_class(fm, path) == "doctrine"

    def test_doctrine_bool_shorthand(self):
        path = PurePosixPath("Inbox/capture.md")
        assert doctrine.resolve_knowledge_class({"doctrine": True}, path) == "doctrine"
        assert doctrine.resolve_knowledge_class({"doctrine": False}, path) == "operational"

    def test_unambiguous_types_classify_anywhere(self):
        path = PurePosixPath("Areas/Reading/ch01.md")
        for t in ("book-moc", "book-chapter", "video-distillation", "distilled"):
            assert doctrine.resolve_knowledge_class({"type": t}, path) == "doctrine"

    def test_ambiguous_types_do_not_classify(self):
        # Audit of a real vault: `reference`, `framework`, `guide`, `source`
        # and `concept` are used on project notes too. They must fall
        # through to the PARA rule, not force doctrine.
        path = PurePosixPath("Projects/Acme/AcmeTests.md")
        for t in ("reference", "framework", "guide", "source", "concept"):
            assert doctrine.resolve_knowledge_class({"type": t}, path) == "operational"

    def test_para_fallback(self):
        def klass(path: str) -> str:
            return doctrine.resolve_knowledge_class({}, PurePosixPath(path))

        assert klass("Resources/Books/x.md") == "doctrine"
        assert klass("Archive/old.md") == "archive"
        assert klass("Projects/p/x.md") == "operational"

    def test_never_raises_on_garbage_frontmatter(self):
        path = PurePosixPath("x.md")
        assert doctrine.resolve_knowledge_class(
            {"knowledge_class": 42, "type": None, "tags": "single"}, path
        ) == "operational"


class TestNoteDomains:
    def test_domain_field_wins(self):
        fm = {"domain": ["Testing", "quality"], "tags": ["book", "misc"]}
        assert doctrine.note_domains(fm) == ["testing", "quality"]

    def test_tags_fallback_drops_generic(self):
        fm = {"tags": ["book", "moc", "shift-left", "ci-cd"]}
        assert doctrine.note_domains(fm) == ["shift-left", "ci-cd"]


# ─── derived query ───────────────────────────────────────────────────────


def _vocab_file(tmp_path: Path, vocab: dict) -> Path:
    path = tmp_path / "doctrine-domains.json"
    path.write_text(json.dumps(vocab), encoding="utf-8")
    return path


VOCAB = {
    "testing": {"count": 40, "cooccurs": {"quality": 20, "shift-left": 12}},
    "quality": {"count": 25, "cooccurs": {"testing": 20}},
    "projections": {"count": 3, "cooccurs": {}},
    "validation": {"count": 8, "cooccurs": {"customer-discovery": 5}},
    "api": {"count": 30, "cooccurs": {"rest": 10}},
}


class TestDeriveDoctrineQuery:
    def test_shared_stem_matches_tests_to_testing(self, tmp_path):
        # "gba-tests" must reach the "testing" domain: hyphens split,
        # "tests" and "testing" share the stem "test".
        vp = _vocab_file(tmp_path, VOCAB)
        query = doctrine.derive_doctrine_query(
            "validate the acme-tests suite structure", vocab_path=vp
        )
        assert "testing" in query
        assert query.endswith("best practices patterns principles")

    def test_loose_prefix_regression_projeto_projections(self, tmp_path):
        # Live-replay regression: pt "projeto" must NOT match "projections"
        # (a prefix-based matcher did exactly that).
        vp = _vocab_file(tmp_path, VOCAB)
        query = doctrine.derive_doctrine_query(
            "descreve o projeto e o seu percurso", vocab_path=vp
        )
        assert "projections" not in query

    def test_pt_alias_reaches_english_domain(self, tmp_path):
        vp = _vocab_file(tmp_path, VOCAB)
        query = doctrine.derive_doctrine_query(
            "boas práticas de testes automatizados", vocab_path=vp
        )
        assert "testing" in query

    def test_rich_match_not_diluted_by_cooccurrence(self, tmp_path):
        # 3+ direct matches: co-occurrence fill must not run (it dragged
        # neighbor-collection noise into queries in live replay).
        vp = _vocab_file(tmp_path, VOCAB)
        query = doctrine.derive_doctrine_query(
            "testing quality validation of the api", vocab_path=vp
        )
        assert "customer-discovery" not in query

    def test_no_match_yields_empty(self, tmp_path):
        vp = _vocab_file(tmp_path, VOCAB)
        assert doctrine.derive_doctrine_query("que horas sao os standups", vocab_path=vp) == ""

    def test_missing_vocab_yields_empty(self, tmp_path):
        assert doctrine.derive_doctrine_query("testing", vocab_path=tmp_path / "nope.json") == ""

    def test_marca_verb_does_not_alias_to_brand(self, tmp_path):
        # Validation-matrix regression (2026-07-30): "marca a reuniao"
        # (schedule the meeting) must not derive a branding query.
        vp = _vocab_file(tmp_path, {**VOCAB, "branding": {"count": 10, "cooccurs": {}}})
        assert doctrine.derive_doctrine_query(
            "marca a reuniao de amanha e avisa a equipa", vocab_path=vp
        ) == ""

    def test_thin_match_fills_from_strongest_domain_only(self, tmp_path):
        # A broad 1-count co-match must not contribute its co-occurrences;
        # only the strongest matched domain fills a thin match.
        vocab = {
            "zettelkasten": {"count": 15, "cooccurs": {"note-taking": 15, "pkm": 15}},
            "organization": {"count": 1, "cooccurs": {"kafka": 3, "event-driven": 3}},
        }
        vp = _vocab_file(tmp_path, vocab)
        query = doctrine.derive_doctrine_query(
            "organiza as notas com zettelkasten", vocab_path=vp
        )
        assert "note-taking" in query
        assert "kafka" not in query and "event-driven" not in query


# ─── retrieval filter + rendering ────────────────────────────────────────


class _FakeStore:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, top_k=5):
        return self._hits


def _hit(source, kclass, score=0.6, retrieval="semantic"):
    return {
        "text": "chunk text", "heading": "H", "source": source,
        "score": score, "retrieval": retrieval,
        "metadata": {"knowledge_class": kclass},
    }


class TestDoctrineNotes:
    def test_filters_to_doctrine_class_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "testing q"
        )
        store = _FakeStore([
            _hit("/v/Projects/note.md", "operational"),
            _hit("/v/Resources/Books/ch.md", "doctrine"),
            _hit("/v/anywhere/tagged.md", "doctrine"),
        ])
        hits = doctrine.doctrine_notes(store, "prompt", set())
        assert [h["source"] for h in hits] == [
            "/v/Resources/Books/ch.md", "/v/anywhere/tagged.md",
        ]

    def test_keyword_degraded_yields_nothing(self, monkeypatch):
        # HONESTY: keyword hits carry no similarity — never present them
        # as doctrine relevance.
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "testing q"
        )
        store = _FakeStore([
            _hit("/v/Resources/Books/ch.md", "doctrine", retrieval="keyword-degraded"),
        ])
        assert doctrine.doctrine_notes(store, "prompt", set()) == []

    def test_excludes_sources_already_in_primary_pass(self, monkeypatch):
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "testing q"
        )
        store = _FakeStore([_hit("/v/Resources/Books/ch.md", "doctrine")])
        assert doctrine.doctrine_notes(
            store, "prompt", {"/v/Resources/Books/ch.md"}
        ) == []

    def test_collection_with_more_chunks_wins_flat_score_band(self, monkeypatch):
        # Validation-matrix regression (2026-07-30): 3 chunks at 0.575 from
        # the topically-right book must outrank lone 0.577 strays — and the
        # bonus counts per COLLECTION (parent folder), because chunk
        # boundaries move between index builds: the same book's matches
        # landed in one file on one build and across chapters on the next.
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "notes q"
        )
        store = _FakeStore([
            _hit("/v/Books/LDD/moc.md", "doctrine", score=0.577),
            _hit("/v/Books/Philosophy/moc.md", "doctrine", score=0.575),
            _hit("/v/Books/SmartNotes/ch01.md", "doctrine", score=0.575),
            _hit("/v/Books/SmartNotes/ch03.md", "doctrine", score=0.575),
            _hit("/v/Books/SmartNotes/ch12.md", "doctrine", score=0.574),
        ])
        hits = doctrine.doctrine_notes(store, "prompt", set())
        assert hits[0]["source"].startswith("/v/Books/SmartNotes/")

    def test_coherence_bonus_is_capped_against_volume(self, monkeypatch):
        # Uncapped, a 40-chapter book flooded three unrelated probes by
        # sheer volume (validation matrix 2026-07-30). The bonus breaks
        # near-ties; it must never beat a real score gap.
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "q"
        )
        big_book = [
            _hit(f"/v/Books/BigBook/ch{i:02d}.md", "doctrine", score=0.560)
            for i in range(10)
        ]
        store = _FakeStore([
            _hit("/v/Books/RightBook/ch1.md", "doctrine", score=0.590),
            *big_book,
        ])
        hits = doctrine.doctrine_notes(store, "prompt", set())
        assert hits[0]["source"] == "/v/Books/RightBook/ch1.md"

    def test_store_error_fails_open(self, monkeypatch):
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "testing q"
        )

        class _Broken:
            def search(self, *a, **k):
                raise RuntimeError("boom")

        assert doctrine.doctrine_notes(_Broken(), "prompt", set()) == []

    def test_block_renders_marker_and_paths(self, monkeypatch):
        monkeypatch.setattr(
            doctrine, "derive_doctrine_query", lambda p, vocab_path=None: "testing q"
        )
        store = _FakeStore([_hit("/v/Resources/Books/ch.md", "doctrine")])
        block = doctrine.doctrine_block(store, "prompt")
        assert block.startswith("[arka:doctrine]")
        assert "/v/Resources/Books/ch.md" in block


# ─── indexer metadata contract ───────────────────────────────────────────


class TestIndexerMetadata:
    def test_chunks_carry_class_and_posix_path(self, tmp_path):
        from core.knowledge.indexer import index_directory

        vault = tmp_path / "vault"
        book_dir = vault / "Resources" / "Books" / "T"
        book_dir.mkdir(parents=True)
        (book_dir / "ch1.md").write_text(
            "---\ntype: book-chapter\ndomain: [testing]\n---\n\n"
            + "word " * 60,
            encoding="utf-8",
        )
        proj_dir = vault / "Projects" / "P"
        proj_dir.mkdir(parents=True)
        (proj_dir / "plan.md").write_text("# plan\n\n" + "word " * 60, encoding="utf-8")

        collected = []

        class _CaptureStore:
            def is_file_indexed(self, *a):
                return False

            def remove_file(self, *a):
                return None

            def index_chunks(self, texts, headings, source, file_hash, metadata):
                collected.append(metadata)
                return len(texts)

            def distinct_source_metadata(self):
                return []

        result = index_directory(
            vault, _CaptureStore(), write_vocabulary=False
        )
        assert result["doctrine_notes"] == 1
        by_class = {m["knowledge_class"]: m for m in collected}
        assert by_class["doctrine"]["relative_path"] == "Resources/Books/T/ch1.md"
        assert "\\" not in by_class["operational"]["relative_path"]
        assert by_class["doctrine"]["domains"] == ["testing"]

    def test_vocabulary_sidecar_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            doctrine, "DEFAULT_VOCAB_PATH", tmp_path / "vocab.json"
        )
        vocab: dict = {}
        doctrine.update_vocabulary(vocab, ["testing", "quality"], "ch1")
        doctrine.update_vocabulary(vocab, ["testing"], "ch2")
        path = doctrine.save_vocabulary(vocab, tmp_path / "vocab.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["testing"]["count"] == 2
        assert data["testing"]["cooccurs"]["quality"] == 1

    def test_incremental_run_rebuilds_vocabulary_from_whole_store(
        self, tmp_path, monkeypatch
    ):
        # An incremental run that skips every file must still write a
        # vocabulary describing the WHOLE index — a per-run vocabulary
        # would overwrite the sidecar with a fragment and blind the
        # doctrine pass to the rest of the corpus.
        from core.knowledge.indexer import index_directory

        vault = tmp_path / "vault"
        (vault / "Resources").mkdir(parents=True)
        (vault / "Resources" / "old.md").write_text(
            "---\ntype: book-chapter\ndomain: [testing]\n---\n\n"
            + "word " * 60,
            encoding="utf-8",
        )
        vocab_path = tmp_path / "vocab.json"
        monkeypatch.setattr(doctrine, "DEFAULT_VOCAB_PATH", vocab_path)

        class _AlreadyIndexedStore:
            def is_file_indexed(self, *a):
                return True  # incremental run: nothing to do

            def distinct_source_metadata(self):
                return [
                    ("/v/Resources/Books/T/ch1.md",
                     {"knowledge_class": "doctrine", "domains": ["testing"]}),
                    ("/v/Resources/Books/T/ch2.md",
                     {"knowledge_class": "doctrine", "domains": ["testing", "quality"]}),
                    ("/v/Projects/plan.md",
                     {"knowledge_class": "operational", "domains": []}),
                ]

        result = index_directory(vault, _AlreadyIndexedStore())
        assert result["files_indexed"] == 0
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        assert data["testing"]["count"] == 2  # whole store, not this run
        assert "quality" in data


# ─── research-gate vault resolution ──────────────────────────────────────


class TestVaultResolution:
    def test_config_key_wins(self, tmp_path, monkeypatch):
        from core.workflow import research_gate

        vault = tmp_path / "vault"
        vault.mkdir()
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"knowledge": {"vaultPath": str(vault)}}), encoding="utf-8"
        )
        monkeypatch.setattr(research_gate, "CONFIG_PATH", cfg)
        monkeypatch.delenv("ARKAOS_VAULT", raising=False)
        assert research_gate._resolve_vault_path() == vault

    def test_env_fallback(self, tmp_path, monkeypatch):
        from core.workflow import research_gate

        vault = tmp_path / "envvault"
        vault.mkdir()
        monkeypatch.setattr(research_gate, "CONFIG_PATH", tmp_path / "none.json")
        monkeypatch.setenv("ARKAOS_VAULT", str(vault))
        assert research_gate._resolve_vault_path() == vault

    def test_none_when_unconfigured(self, tmp_path, monkeypatch):
        from core.workflow import research_gate

        monkeypatch.setattr(research_gate, "CONFIG_PATH", tmp_path / "none.json")
        monkeypatch.delenv("ARKAOS_VAULT", raising=False)
        assert research_gate._resolve_vault_path() is None


# ─── grounding quarantine (QG C2) ────────────────────────────────────────
#
# dreaming.py promises that "Synapse L2.5 reads this marker and excludes
# (or explicitly labels) these notes so they never masquerade as grounded
# KB". The doctrine block is an L2.5 injection and used to do neither,
# while presenting its notes as "livros/vídeos/frameworks ingeridos" — the
# one claim a generated note can never satisfy.


class _StubStore:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, top_k=5):
        return self._hits


def _doctrine_hit(source, score=0.91, inferred=False):
    metadata = {"knowledge_class": "doctrine"}
    if inferred:
        metadata["grounding"] = "inferred"
    return {
        "source": source, "score": score, "text": "conteudo " * 20,
        "heading": "", "metadata": metadata,
    }


@pytest.fixture
def vocab(tmp_path):
    path = tmp_path / "vocab.json"
    path.write_text(
        json.dumps({"architecture": {"count": 5, "notes": ["n"]}}),
        encoding="utf-8",
    )
    return path


def test_inferred_note_is_labelled_not_presented_as_doctrine(tmp_path, vocab):
    """A generated note may only reach the reader wearing the label."""
    store = _StubStore([_doctrine_hit(str(tmp_path / "dream.md"), inferred=True)])
    hits = doctrine.doctrine_notes(store, "arquitetura do sistema", set(), vocab)

    assert hits, "quarantine must label, not silently empty the block"
    assert hits[0]["inferred"] is True
    block = doctrine.format_doctrine_block(hits)
    assert "(inferida — não autoritativa)" in block


def test_inferred_notes_are_dropped_when_grounded_doctrine_suffices(
    tmp_path, vocab
):
    """Same rule as the sibling block: excluded outright once two grounded
    notes matched, admitted only to fill a thin block."""
    store = _StubStore([
        _doctrine_hit(str(tmp_path / "book1.md"), score=0.95),
        _doctrine_hit(str(tmp_path / "book2.md"), score=0.94),
        _doctrine_hit(str(tmp_path / "dream.md"), score=0.93, inferred=True),
    ])
    hits = doctrine.doctrine_notes(store, "arquitetura do sistema", set(), vocab)

    sources = [h["source"] for h in hits]
    assert str(tmp_path / "dream.md") not in sources
    assert len(hits) == 2


def test_grounded_doctrine_carries_no_label(tmp_path, vocab):
    store = _StubStore([_doctrine_hit(str(tmp_path / "book.md"))])
    hits = doctrine.doctrine_notes(store, "arquitetura do sistema", set(), vocab)

    assert hits[0]["inferred"] is False
    assert "inferida" not in doctrine.format_doctrine_block(hits)


def test_both_blocks_use_the_same_label_text():
    """The operator sees both blocks in one prompt; a note must not be
    authoritative in one wording and not the other."""
    from core.synapse import layers_kb

    source = (REPO_ROOT / "core" / "synapse" / "layers_kb.py").read_text(
        encoding="utf-8"
    )
    assert "(inferida — não autoritativa)" in source
    assert layers_kb is not None
