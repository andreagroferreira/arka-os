"""Tests for core.memory.semantic_store (F1-A2)."""

from __future__ import annotations

import sqlite3

import pytest

from core.memory.semantic_store import SessionMemoryStore, TurnRecord


@pytest.fixture
def store(tmp_path):
    return SessionMemoryStore(tmp_path / "session-memory.db")


def _record(**kwargs) -> TurnRecord:
    base = dict(
        ts="2026-07-11T10:00:00+00:00",
        session_id="sess-1",
        project_name="proj",
        summary="implemented the payment retry queue",
    )
    base.update(kwargs)
    return TurnRecord(**base)


def test_save_and_recent_roundtrip(store):
    store.save(_record(id="t1"))
    store.save(_record(id="t2", ts="2026-07-11T11:00:00+00:00", importance=0.9))
    records = store.recent(project_name="proj")
    assert [r.id for r in records] == ["t2", "t1"]  # importance then recency
    assert records[0].tools_used == []


def test_recent_scopes_project_and_session(store):
    store.save(_record(id="mine", project_name="proj", session_id="s1"))
    store.save(_record(id="other-proj", project_name="other"))
    store.save(_record(id="same-sess", session_id="skip-me"))
    ids = {r.id for r in store.recent(project_name="proj", exclude_session="skip-me")}
    assert ids == {"mine"}


def test_keyword_search_is_labeled_degraded(store):
    store.save(_record(id="t1", summary="payment retry queue design"))
    hits = store.keyword_search("payment queue", project_name="proj")
    assert len(hits) == 1
    assert hits[0]["retrieval"] == "keyword-degraded"
    assert hits[0]["score"] is None  # no similarity exists — never fake one


def test_keyword_search_short_words_ignored(store):
    store.save(_record(id="t1"))
    assert store.keyword_search("a of") == []


def test_semantic_neighbors_orders_by_cosine(store):
    store.save(_record(id="near", embedding=[1.0, 0.0], dims=2,
                       embedding_backend="fastembed"))
    store.save(_record(id="far", embedding=[0.0, 1.0], dims=2,
                       embedding_backend="fastembed"))
    hits = store.semantic_neighbors([1.0, 0.1], project_name="proj")
    assert [h["id"] for h in hits] == ["near", "far"]
    assert all(h["retrieval"] == "semantic" for h in hits)
    assert hits[0]["score"] > hits[1]["score"]


def test_semantic_neighbors_skips_mismatched_dims(store):
    """Vectors from different backends are incomparable — never compared."""
    store.save(_record(id="ok", embedding=[1.0, 0.0], dims=2))
    store.save(_record(id="alien", embedding=[1.0, 0.0, 0.0], dims=3))
    hits = store.semantic_neighbors([1.0, 0.0], project_name="proj")
    assert [h["id"] for h in hits] == ["ok"]


def test_semantic_neighbors_excludes_session(store):
    store.save(_record(id="own", session_id="current", embedding=[1.0], dims=1))
    store.save(_record(id="cross", session_id="older", embedding=[1.0], dims=1))
    hits = store.semantic_neighbors([1.0], exclude_session="current")
    assert [h["id"] for h in hits] == ["cross"]


def test_backfill_and_update_embedding(store):
    store.save(_record(id="pending", embedding=None))
    candidates = store.backfill_candidates()
    assert [c.id for c in candidates] == ["pending"]
    store.update_embedding("pending", [0.5, 0.5], "ollama", "nomic-embed-text")
    assert store.backfill_candidates() == []
    stats = store.stats()
    assert stats["by_embedding_backend"].get("ollama") == 1


def test_prune_by_age_and_cap(store):
    store.save(_record(id="ancient", ts="2020-01-01T00:00:00+00:00"))
    store.save(_record(id="fresh", ts="2026-07-11T10:00:00+00:00"))
    removed = store.prune(retention_days=90, max_rows=10)
    assert removed == 1
    assert {r.id for r in store.recent()} == {"fresh"}


def test_store_born_self_healing(tmp_path):
    db = tmp_path / "session-memory.db"
    SessionMemoryStore(db)  # create real schema
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO turns (id, ts, session_id, summary) VALUES (?,?,?,?)",
        [(f"t{i}", "2026-07-11T10:00:00+00:00", "s", "x" * 200) for i in range(300)],
    )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    # Corrupt from the end until detectable (same fixture as sqlite_recovery).
    size = db.stat().st_size
    for i in range(1, 17):
        with db.open("r+b") as fh:
            fh.seek(max(0, size - 512 * i))
            fh.write(b"X" * 512)
        probe = sqlite3.connect(db)
        try:
            ok = str(probe.execute("PRAGMA quick_check(1)").fetchone()[0]).lower() == "ok"
        except sqlite3.DatabaseError:
            ok = False
        finally:
            probe.close()
        if not ok:
            break
    from core.shared.sqlite_recovery import recover

    result = recover(db)
    assert result.recovered
    assert result.rows_recovered > 0
    store = SessionMemoryStore(db)
    assert store.stats()["total_turns"] > 0  # healed, never emptied
