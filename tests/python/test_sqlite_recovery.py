"""Tests for core.shared.sqlite_recovery (F1-D1).

The central invariant under test: a self-heal must never silently empty
the live store. Corruption fixtures damage REAL pages of REAL schemas,
and the assertions count surviving rows — not just "didn't raise".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.shared.sqlite_recovery import (
    RecoveryResult,
    main,
    open_with_recovery,
    recover,
)

CAPTURES_SCHEMA = """CREATE TABLE captures (
    id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, session_id TEXT NOT NULL,
    project_path TEXT NOT NULL, project_name TEXT NOT NULL,
    category TEXT NOT NULL, content TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '{}',
    processed INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0)"""


def _make_db(path: Path, rows_a: int = 5, rows_b: int = 200) -> None:
    """Two-table DB, small pages so single-page corruption stays surgical."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA page_size=512")
    conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("CREATE TABLE b (id INTEGER PRIMARY KEY, val TEXT)")
    conn.executemany(
        "INSERT INTO a (val) VALUES (?)", [(f"a-{i}",) for i in range(rows_a)]
    )
    conn.executemany(
        "INSERT INTO b (val) VALUES (?)", [(f"b-{i}" * 20,) for i in range(rows_b)]
    )
    conn.commit()
    conn.close()


def _make_captures_db(path: Path, rows: int = 300) -> None:
    """The REAL CaptureStore schema — the single-table production case."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA page_size=512")
    conn.execute(CAPTURES_SCHEMA)
    conn.executemany(
        "INSERT INTO captures (id,timestamp,session_id,project_path,"
        "project_name,category,content) VALUES (?,?,?,?,?,?,?)",
        [
            (f"id{i}", "2026-01-01T00:00:00+00:00", "s", "/p", "proj", "cat",
             "content-" + ("x" * 80))
            for i in range(rows)
        ],
    )
    conn.commit()
    conn.close()


def _corrupt_last_page(path: Path) -> None:
    size = path.stat().st_size
    with path.open("r+b") as fh:
        fh.seek(size - 512)
        fh.write(b"X" * 512)


def _quick_ok(path: Path) -> bool:
    conn = sqlite3.connect(path)
    try:
        return str(conn.execute("PRAGMA quick_check(1)").fetchone()[0]).lower() == "ok"
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def _count(path: Path, table: str) -> int:
    quoted = table.replace('"', '""')
    count_sql = f'SELECT COUNT(*) FROM "{quoted}"'  # identifier quoted above
    conn = sqlite3.connect(path)
    try:
        return conn.execute(count_sql).fetchone()[0]
    finally:
        conn.close()


def _corrupt_until_detected(path: Path, max_blocks: int = 16) -> None:
    """Corrupt 512-byte blocks from the end until quick_check flags it —
    deterministic regardless of page size or trailing free pages."""
    size = path.stat().st_size
    for i in range(1, max_blocks + 1):
        with path.open("r+b") as fh:
            fh.seek(max(0, size - 512 * i))
            fh.write(b"X" * 512)
        if not _quick_ok(path):
            return
    raise AssertionError("could not produce detectable corruption")


# ─── recover() outcomes ────────────────────────────────────────────────


def test_missing_db(tmp_path):
    assert recover(tmp_path / "nope.db") == RecoveryResult(reason="no-db")


def test_healthy_db_untouched(tmp_path):
    db = tmp_path / "ok.db"
    _make_db(db)
    before = db.read_bytes()
    result = recover(db)
    assert result.reason == "not-corrupt"
    assert not result.recovered
    assert db.read_bytes() == before
    assert not list(tmp_path.glob("*.bak"))


def test_corrupt_db_partial_salvage(tmp_path):
    """One bad page loses only that page's rows — never the whole table."""
    db = tmp_path / "hurt.db"
    _make_db(db)
    _corrupt_last_page(db)
    assert not _quick_ok(db), "corruption must be detectable for this test"
    result = recover(db)
    assert result.recovered
    assert result.backup_path and Path(result.backup_path).exists()
    assert _quick_ok(db)
    assert _count(db, "a") == 5  # undamaged table survives whole
    assert _count(db, "b") >= 150  # damaged table keeps its healthy pages


def test_single_table_store_never_heals_to_empty(tmp_path):
    """QG blocker B1: the production single-table case must keep rows."""
    db = tmp_path / "captures.db"
    _make_captures_db(db, rows=300)
    _corrupt_last_page(db)
    assert not _quick_ok(db)
    result = recover(db)
    assert result.recovered
    assert result.rows_recovered > 0
    assert _count(db, "captures") > 0
    assert _count(db, "captures") >= 150  # most healthy pages survive


def test_hostile_table_name_salvaged(tmp_path):
    """QG blocker B2: quoted identifiers at every site (walk/count/verify)."""
    db = tmp_path / "weird.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA page_size=512")
    conn.execute('CREATE TABLE "we""ird" (id INTEGER PRIMARY KEY, val TEXT)')
    conn.executemany(
        'INSERT INTO "we""ird" (val) VALUES (?)', [(f"v{i}",) for i in range(7)]
    )
    conn.execute("CREATE TABLE big (id INTEGER PRIMARY KEY, val TEXT)")
    conn.executemany(
        "INSERT INTO big (val) VALUES (?)", [("z" * 100,) for _ in range(200)]
    )
    conn.commit()
    conn.close()
    _corrupt_last_page(db)
    assert not _quick_ok(db)
    result = recover(db)
    assert result.recovered
    assert _count(db, 'we"ird') == 7  # fully salvaged, not silently dropped


def test_garbage_file_left_untouched(tmp_path):
    db = tmp_path / "junk.db"
    db.write_bytes(b"this was never a sqlite file" * 10)
    before = db.read_bytes()
    result = recover(db)
    assert not result.recovered
    assert db.read_bytes() == before
    assert not list(tmp_path.glob("*.recovering-*"))


def test_writer_active_never_races(tmp_path):
    db = tmp_path / "busy.db"
    _make_db(db)
    _corrupt_last_page(db)
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        result = recover(db)
        assert result == RecoveryResult(reason="writer-active")
    finally:
        holder.execute("ROLLBACK")
        holder.close()


# ─── open_with_recovery ────────────────────────────────────────────────


def test_open_with_recovery_passthrough(tmp_path):
    db = tmp_path / "fine.db"
    _make_db(db)
    assert open_with_recovery(db, lambda: "opened") == "opened"


def test_open_with_recovery_unsalvageable_propagates(tmp_path):
    db = tmp_path / "healme.db"
    db.write_bytes(b"garbage")
    calls = {"n": 0}

    def opener():
        calls["n"] += 1
        conn = sqlite3.connect(db)
        try:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            conn.close()
        return "ok"

    # Garbage cannot be salvaged -> recover fails -> original error propagates.
    with pytest.raises(sqlite3.DatabaseError):
        open_with_recovery(db, opener)
    assert calls["n"] == 1


def test_open_with_recovery_retry_after_heal(tmp_path):
    db = tmp_path / "retry.db"
    _make_db(db)
    _corrupt_last_page(db)
    assert not _quick_ok(db)

    def opener():
        conn = sqlite3.connect(db)
        try:
            row = conn.execute("PRAGMA quick_check(1)").fetchone()
            if str(row[0]).lower() != "ok":
                raise sqlite3.DatabaseError("still corrupt")
            return "healed"
        finally:
            conn.close()

    assert open_with_recovery(db, opener) == "healed"


# ─── Store integration — REAL trigger, NO monkeypatch ──────────────────


def test_capture_store_self_heals_with_survivors(tmp_path):
    """Real store, real corruption, real __init__ trigger (QG repro)."""
    from core.cognition.capture.store import CaptureStore

    db = tmp_path / "captures.db"
    _make_captures_db(db, rows=300)
    _corrupt_last_page(db)
    assert not _quick_ok(db)
    store = CaptureStore(str(db))  # must not raise
    assert _quick_ok(db)
    assert list(tmp_path.glob("*.corrupt-*.bak"))
    assert _count(db, "captures") > 0  # healed store is NOT empty
    assert store.stats() is not None


def test_vector_store_self_heals_with_survivors(tmp_path, monkeypatch):
    """Real VectorStore schema + rows; opener's first raise is simulated
    (index-heavy schemas don't always trip on connect), but corruption,
    salvage, verify, .bak and the surviving-rows assertion are real."""
    from core.knowledge.vector_store import VectorStore

    db = tmp_path / "knowledge.db"
    VectorStore(db)  # create the real schema
    conn = sqlite3.connect(db)
    conn.executemany(
        "INSERT INTO chunks (text, heading, source, metadata) VALUES (?,?,?,?)",
        [(f"chunk-{i} " + "y" * 100, "h", "src.md", "{}") for i in range(200)],
    )
    conn.commit()
    # Flush the WAL into the main file so byte corruption is visible.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    _corrupt_until_detected(db)
    assert not _quick_ok(db)
    orig_open = VectorStore._open
    calls = {"n": 0}

    def flaky_open(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.DatabaseError("database disk image is malformed")
        return orig_open(self)

    monkeypatch.setattr(VectorStore, "_open", flaky_open)
    store = VectorStore(db)  # must not raise
    assert calls["n"] == 2
    assert _count(db, "chunks") > 0  # healed store is NOT empty
    assert list(tmp_path.glob("*.corrupt-*.bak"))
    assert store.get_stats() is not None


# ─── CLI ───────────────────────────────────────────────────────────────


def test_cli_healthy(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _make_db(db)
    assert main([str(db)]) == 0
    assert '"not-corrupt"' in capsys.readouterr().out


def test_cli_usage():
    assert main([]) == 2
