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
                       embedding_backend="fastembed", embedding_model="m1"))
    store.save(_record(id="far", embedding=[0.0, 1.0], dims=2,
                       embedding_backend="fastembed", embedding_model="m1"))
    hits = store.semantic_neighbors([1.0, 0.1], project_name="proj",
                                    backend="fastembed", model="m1")
    assert [h["id"] for h in hits] == ["near", "far"]
    assert all(h["retrieval"] == "semantic" for h in hits)
    assert hits[0]["score"] > hits[1]["score"]


def test_semantic_neighbors_skips_mismatched_dims(store):
    store.save(_record(id="ok", embedding=[1.0, 0.0], dims=2))
    store.save(_record(id="alien", embedding=[1.0, 0.0, 0.0], dims=3))
    hits = store.semantic_neighbors([1.0, 0.0], project_name="proj",
                                    backend="none", model="")
    assert [h["id"] for h in hits] == ["ok"]


def test_semantic_neighbors_skips_other_vector_spaces(store):
    """QG blocker E2: same dims from a different backend/model is NOT
    comparable — cosine across spaces is a meaningless number."""
    store.save(_record(id="mine", embedding=[1.0, 0.0], dims=2,
                       embedding_backend="fastembed", embedding_model="bge"))
    store.save(_record(id="alien-backend", embedding=[1.0, 0.0], dims=2,
                       embedding_backend="ollama", embedding_model="nomic"))
    store.save(_record(id="alien-model", embedding=[1.0, 0.0], dims=2,
                       embedding_backend="fastembed", embedding_model="minilm"))
    hits = store.semantic_neighbors([1.0, 0.0], project_name="proj",
                                    backend="fastembed", model="bge")
    assert [h["id"] for h in hits] == ["mine"]


def test_semantic_neighbors_excludes_session(store):
    store.save(_record(id="own", session_id="current", embedding=[1.0], dims=1))
    store.save(_record(id="cross", session_id="older", embedding=[1.0], dims=1))
    hits = store.semantic_neighbors([1.0], exclude_session="current",
                                    backend="none", model="")
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


def test_runtime_roundtrip_and_default(store):
    store.save(_record(id="oc", runtime="opencode"))
    store.save(_record(id="cl", runtime="claude"))
    store.save(_record(id="legacy"))  # pre-runtime records default to ""
    records = {r.id: r for r in store.recent()}
    assert records["oc"].runtime == "opencode"
    assert records["cl"].runtime == "claude"
    assert records["legacy"].runtime == ""


def test_runtime_column_migrated_on_existing_db(tmp_path):
    """DBs created before the runtime column existed get it via ALTER —
    CREATE TABLE IF NOT EXISTS never touches a live table."""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE turns (
            id TEXT PRIMARY KEY, ts TEXT NOT NULL, session_id TEXT NOT NULL,
            project_name TEXT NOT NULL DEFAULT '', cwd TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '', tools_used TEXT NOT NULL DEFAULT '[]',
            file_paths TEXT NOT NULL DEFAULT '[]', importance REAL NOT NULL DEFAULT 0.5,
            embedding TEXT, embedding_backend TEXT NOT NULL DEFAULT 'none',
            embedding_model TEXT NOT NULL DEFAULT '', dims INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "INSERT INTO turns (id, ts, session_id, summary) VALUES (?,?,?,?)",
        ("old-row", "2026-07-11T10:00:00+00:00", "s", "legacy summary"),
    )
    conn.commit()
    conn.close()
    store = SessionMemoryStore(db)
    store.save(_record(id="new-row", runtime="opencode"))
    records = {r.id: r for r in store.recent()}
    assert records["new-row"].runtime == "opencode"
    assert records["old-row"].runtime == ""  # backfilled default, not a crash


def test_latest_turn_scopes_and_excludes(store):
    store.save(_record(id="old", ts="2026-07-11T09:00:00+00:00",
                       session_id="s1", runtime="claude"))
    store.save(_record(id="new", ts="2026-07-11T11:00:00+00:00",
                       session_id="s2", runtime="opencode"))
    store.save(_record(id="other-proj", project_name="other",
                       ts="2026-07-11T12:00:00+00:00"))
    latest = store.latest_turn("proj")
    assert latest is not None and latest.id == "new"
    assert store.latest_turn("proj", exclude_session="s2").id == "old"
    assert store.latest_turn("missing-proj") is None


def test_cross_runtime_handoff(store):
    from datetime import UTC, datetime, timedelta

    fresh = datetime.now(UTC).isoformat()
    store.save(_record(id="from-oc", ts=fresh, runtime="opencode",
                       session_id="oc-1"))
    hit = store.cross_runtime_handoff("proj", "claude")
    assert hit is not None and hit.id == "from-oc"
    assert store.cross_runtime_handoff("proj", "opencode") is None  # same
    assert store.cross_runtime_handoff(
        "proj", "claude", exclude_session="oc-1") is None


def test_cross_runtime_handoff_rejects_stale_and_legacy(store, tmp_path):
    from datetime import UTC, datetime, timedelta

    fresh = datetime.now(UTC).isoformat()
    stale = (datetime.now(UTC) - timedelta(hours=48)).isoformat()

    stale_db = SessionMemoryStore(tmp_path / "stale.db")
    stale_db.save(_record(id="old-oc", ts=stale, runtime="opencode"))
    assert stale_db.cross_runtime_handoff("proj", "claude") is None

    legacy_db = SessionMemoryStore(tmp_path / "legacy.db")
    legacy_db.save(_record(id="legacy", ts=fresh, runtime=""))
    assert legacy_db.cross_runtime_handoff("proj", "claude") is None


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
