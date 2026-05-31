"""Integration tests for /api/knowledge/sources/* + upload traversal guard.

Covers the two P1 blockers fixed in feat/knowledge-video-pipeline:
  1. ``_get_source_registry`` was undefined -> every sources/* endpoint 500'd.
  2. upload-file used the raw client filename -> arbitrary file write.

Tests use a real (tmp) SourceRegistry so the endpoint<->registry wiring is
exercised end to end. The real ~/.arkaos is never touched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    """Load scripts/dashboard-api.py as an importable module (matches the
    loader pattern used by the other dashboard-api test files)."""
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def registry(tmp_path):
    """A real SourceRegistry over a throwaway knowledge.db."""
    from core.knowledge.sources import SourceRegistry
    return SourceRegistry(tmp_path / "knowledge.db")


@pytest.fixture
def client(dashboard_module, registry, monkeypatch):
    """TestClient with the source registry pinned to the tmp registry so the
    real ~/.arkaos is never read or written."""
    monkeypatch.setattr(dashboard_module, "_get_source_registry", lambda: registry)
    return TestClient(dashboard_module.app)


def test_unknown_source_is_clean_not_found(client):
    """Unknown id must not 500 — the missing helper used to NameError here."""
    res = client.get("/api/knowledge/sources/src-doesnotexist")
    assert res.status_code != 500
    assert res.status_code == 404
    assert res.json().get("error") == "not found"


def test_source_detail_reads_registry_end_to_end(client, registry, monkeypatch, dashboard_module):
    """Insert a row directly, then prove GET returns 200 with its metadata.
    Proves the endpoint<->registry read path is wired correctly."""
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: None)
    sid = registry.upsert(
        "https://example.com/talk",
        title="A Real Talk",
        transcript="hello world transcript",
        status="ready",
    )
    res = client.get(f"/api/knowledge/sources/{sid}")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "A Real Talk"
    assert body["transcript"] == "hello world transcript"
    assert body["chunks"] == []


def test_source_transcript_reads_registry(client, registry):
    sid = registry.upsert("https://example.com/v2", transcript="full transcript text")
    res = client.get(f"/api/knowledge/sources/{sid}/transcript")
    assert res.status_code == 200
    assert res.json()["transcript"] == "full transcript text"


def test_upload_traversal_writes_nothing_outside_media(client, monkeypatch, dashboard_module, tmp_path):
    """filename='../../../../arkaos_pwn_test' must NOT write outside media_dir.
    The basename strip neutralizes the traversal: any write lands safely
    inside media_dir, and the escape targets stay non-existent."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    media_dir = home / ".arkaos" / "media"
    # Would-be escape targets at the levels the payload tried to reach.
    escapes = [home / "arkaos_pwn_test", home / ".arkaos" / "arkaos_pwn_test"]
    for target in escapes:
        assert not target.exists()

    res = client.post(
        "/api/knowledge/upload-file",
        files={"file": ("../../../../arkaos_pwn_test", b"pwned", "text/plain")},
    )
    assert res.status_code == 200
    # Critical invariant: nothing was written outside the media dir.
    for target in escapes:
        assert not target.exists()
    # If anything was written, it is confined to media_dir under the basename.
    stray = list(p for p in tmp_path.rglob("arkaos_pwn_test"))
    for p in stray:
        assert media_dir.resolve() in p.resolve().parents


def test_upload_rejects_empty_basename(client, monkeypatch, dashboard_module, tmp_path):
    """A filename that reduces to an empty basename is rejected outright."""
    home = tmp_path / "home2"
    home.mkdir()
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    res = client.post(
        "/api/knowledge/upload-file",
        files={"file": ("../../../", b"pwned", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json().get("error") == "invalid filename"


def test_get_source_registry_returns_instance(dashboard_module, monkeypatch, tmp_path):
    """When knowledge.db is creatable, the helper yields a real registry."""
    from core.knowledge.sources import SourceRegistry
    monkeypatch.setattr(dashboard_module, "_source_registry_cache", None)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: tmp_path))
    reg = dashboard_module._get_source_registry()
    assert reg is not None
    assert isinstance(reg, SourceRegistry)


# --- _merge_source_rows pure-helper unit tests (list vs registry divergence) ---

def test_merge_store_only_source_is_linkable(dashboard_module):
    """A source only in the vector store gets a computed id and empty title."""
    from core.knowledge.sources import source_id
    merged = dashboard_module._merge_source_rows(
        [{"source": "https://example.com/a", "chunks": 3}], []
    )
    assert len(merged) == 1
    row = merged[0]
    assert row["id"] == source_id("https://example.com/a")
    assert row["chunks"] == 3
    assert row["title"] == ""
    assert row["type"] == ""


def test_merge_registry_only_zero_chunk_ready_source_appears(dashboard_module):
    """A registry source with 0 chunks (status=ready) must appear — the bug fix."""
    reg_row = {
        "id": "src-abc123", "source": "https://example.com/b", "type": "video",
        "title": "Ready But Empty", "media_path": "/m.mp4", "duration": 120,
        "status": "ready",
    }
    merged = dashboard_module._merge_source_rows([], [reg_row])
    assert len(merged) == 1
    row = merged[0]
    assert row["chunks"] == 0
    assert row["id"] == "src-abc123"
    assert row["title"] == "Ready But Empty"
    assert row["has_media"] is True
    assert row["duration"] == 120


def test_merge_source_in_both_is_single_row(dashboard_module):
    """A source in store + registry yields one row: chunks from store, meta from registry."""
    store_rows = [{"source": "https://example.com/c", "chunks": 7}]
    reg_rows = [{"id": "src-c", "source": "https://example.com/c",
                 "title": "Both", "type": "article", "status": "ready"}]
    merged = dashboard_module._merge_source_rows(store_rows, reg_rows)
    assert len(merged) == 1
    row = merged[0]
    assert row["chunks"] == 7
    assert row["id"] == "src-c"
    assert row["title"] == "Both"


def test_merge_empty_id_falls_back_to_source_id(dashboard_module):
    """A registry row with id == '' (or None) must never yield id == ''.

    Facet B: ``setdefault`` was a no-op because ``_registry_fields`` already
    set the key to ''. The row must link to its computed source_id instead.
    """
    from core.knowledge.sources import source_id
    src = "https://example.com/no-id"
    for empty in ("", None):
        reg_row = {"id": empty, "source": src, "title": "No Id", "status": "ready"}
        merged = dashboard_module._merge_source_rows([], [reg_row])
        assert len(merged) == 1
        assert merged[0]["id"] == source_id(src)
        assert merged[0]["id"] != ""


def test_detail_falls_back_to_vector_store_for_chunks_only_source(
    client, monkeypatch, dashboard_module, tmp_path
):
    """A source that exists ONLY in the vector store (no registry row) must
    resolve via the reverse-lookup fallback instead of 404ing.

    Facet A: the list links every row to /knowledge/{id}; pre-registry
    sources have chunks but no registry row.
    """
    from core.knowledge.sources import source_id
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "store.db")
    src = "https://www.youtube.com/watch?v=ABC"
    store.index_chunks(texts=["first chunk text", "second chunk text"], source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)

    res = client.get(f"/api/knowledge/sources/{source_id(src)}")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "youtube"
    assert body["source"] == src
    assert body["chunk_count"] > 0
    assert len(body["chunks"]) == body["chunk_count"]


def test_detail_404_when_neither_registry_nor_store_has_it(
    client, monkeypatch, dashboard_module, tmp_path
):
    """An id absent from both registry and store still 404s cleanly."""
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "empty-store.db")
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)
    res = client.get("/api/knowledge/sources/src-totallyunknown000")
    assert res.status_code == 404
    assert res.json().get("error") == "not found"


def test_list_sources_includes_zero_chunk_registry_row(client, registry, monkeypatch, dashboard_module):
    """GET /api/knowledge/sources surfaces a 0-chunk ready registry row with its id+title.

    Every returned row must carry an ``id`` so the frontend can link it.
    """
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: None)
    sid = registry.upsert(
        "https://example.com/empty-but-ready",
        title="Empty Ready",
        status="ready",
        chunk_count=0,
    )
    res = client.get("/api/knowledge/sources")
    assert res.status_code == 200
    sources = res.json()["sources"]
    assert all("id" in row for row in sources)
    match = [r for r in sources if r["id"] == sid]
    assert len(match) == 1
    assert match[0]["title"] == "Empty Ready"
    assert match[0]["chunks"] == 0


# --- transcript reconstruction from chunks (legacy sources) ---

def test_legacy_transcript_reconstructed_in_order(
    client, monkeypatch, dashboard_module, tmp_path
):
    """Legacy source (chunks, no registry row): /transcript reconstructs the
    full text from chunks joined in ingest order, reconstructed==true."""
    from core.knowledge.sources import source_id
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "legacy-store.db")
    src = "https://youtu.be/legacyABC"
    parts = ["alpha first part", "bravo second part", "charlie third part"]
    store.index_chunks(texts=parts, source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)

    res = client.get(f"/api/knowledge/sources/{source_id(src)}/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["reconstructed"] is True
    assert body["transcript"] == "\n\n".join(parts)
    for part in parts:
        assert part in body["transcript"]


def test_legacy_detail_includes_reconstructed_transcript(
    client, monkeypatch, dashboard_module, tmp_path
):
    """Detail for a legacy source carries the reconstructed transcript and
    transcript_reconstructed==true."""
    from core.knowledge.sources import source_id
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "legacy-detail.db")
    src = "https://youtu.be/legacyDETAIL"
    store.index_chunks(texts=["only chunk text here"], source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)

    res = client.get(f"/api/knowledge/sources/{source_id(src)}")
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "only chunk text here"
    assert body["transcript_reconstructed"] is True


def test_stored_transcript_wins_over_reconstruction(
    client, registry, monkeypatch, dashboard_module, tmp_path
):
    """A registry row with a real stored transcript returns it with
    reconstructed==false, even when chunks exist for the same source."""
    from core.knowledge.vector_store import VectorStore

    src = "https://example.com/stored"
    store = VectorStore(tmp_path / "stored-store.db")
    store.index_chunks(texts=["chunk derived text"], source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)
    sid = registry.upsert(src, transcript="the real stored transcript")

    res = client.get(f"/api/knowledge/sources/{sid}/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "the real stored transcript"
    assert body["reconstructed"] is False


def test_transcript_preserves_insertion_order(
    client, monkeypatch, dashboard_module, tmp_path
):
    """Chunks indexed in a deliberate sequence must rejoin in that same
    order (guards the ORDER BY id in chunks_for_source)."""
    from core.knowledge.sources import source_id
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "order-store.db")
    src = "https://youtu.be/orderTEST"
    ordered = ["111one", "222two", "333three", "444four"]
    store.index_chunks(texts=ordered, source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)

    res = client.get(f"/api/knowledge/sources/{source_id(src)}/transcript")
    assert res.status_code == 200
    transcript = res.json()["transcript"]
    positions = [transcript.index(p) for p in ordered]
    assert positions == sorted(positions)


def test_transcript_404_when_id_matches_nothing(
    client, monkeypatch, dashboard_module, tmp_path
):
    """Unknown id (no registry row, no chunk source) -> /transcript 404."""
    from core.knowledge.vector_store import VectorStore

    store = VectorStore(tmp_path / "empty-transcript.db")
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)
    res = client.get("/api/knowledge/sources/src-nope000/transcript")
    assert res.status_code == 404
    assert res.json().get("error") == "not found"


def test_transcript_dedupes_real_chunker_overlap_seams(
    client, monkeypatch, dashboard_module, tmp_path
):
    """A legacy source whose chunks were produced by the REAL chunker (with
    overlap) reconstructs a transcript with the seam overlap removed: the
    deduped /transcript is measurably shorter than the naive "\\n\\n".join,
    reconstructed==true, and no chunk content is lost."""
    from core.knowledge.chunker import chunk_markdown
    from core.knowledge.sources import source_id
    from core.knowledge.vector_store import VectorStore

    content = " ".join(
        f"Sentence number {i} carries unique content words here." for i in range(80)
    )
    chunks = chunk_markdown(content, max_tokens=60, overlap_tokens=10)
    texts = [c.text for c in chunks]
    assert len(texts) > 1, "fixture must produce multiple overlapping chunks"

    store = VectorStore(tmp_path / "real-chunker-store.db")
    src = "https://youtu.be/realChunkerSeams"
    store.index_chunks(texts=texts, source=src)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: store)

    res = client.get(f"/api/knowledge/sources/{source_id(src)}/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["reconstructed"] is True

    naive = "\n\n".join(texts)
    assert len(body["transcript"]) < len(naive)
    # Word count tracks the original content (overlap removed, content kept).
    assert abs(len(body["transcript"].split()) - len(content.split())) <= 5
    # A distinctive mid-document sentence survives exactly once (no seam dup).
    assert body["transcript"].count(
        "Sentence number 40 carries unique content words here."
    ) == 1
