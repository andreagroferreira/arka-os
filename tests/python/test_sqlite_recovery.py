"""Tests for core.shared.sqlite_recovery (F1-D1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.shared.sqlite_recovery import RecoveryResult, main, open_with_recovery, recover


def _make_db(path: Path, rows_a: int = 5, rows_b: int = 200) -> None:
    """Small page size so single-page corruption stays surgical."""
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


def _corrupt_last_page(path: Path) -> None:
    size = path.stat().st_size
    with path.open("r+b") as fh:
        fh.seek(size - 512)
        fh.write(b"X" * 512)


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


def test_corrupt_db_recovers_with_backup(tmp_path):
    db = tmp_path / "hurt.db"
    _make_db(db)
    _corrupt_last_page(db)
    assert not _quick_ok(db), "corruption must be detectable for this test"
    result = recover(db)
    assert result.recovered
    assert result.backup_path and Path(result.backup_path).exists()
    # Rebuilt DB is healthy and table 'a' (undamaged pages) survived whole.
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT COUNT(*) FROM a").fetchone()[0] == 5
    conn.close()


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


def _quick_ok(path: Path) -> bool:
    conn = sqlite3.connect(path)
    try:
        return str(conn.execute("PRAGMA quick_check(1)").fetchone()[0]).lower() == "ok"
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


# ─── open_with_recovery ────────────────────────────────────────────────


def test_open_with_recovery_passthrough(tmp_path):
    db = tmp_path / "fine.db"
    _make_db(db)
    assert open_with_recovery(db, lambda: "opened") == "opened"


def test_open_with_recovery_heals_once(tmp_path):
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


# ─── Store integration (real stores born self-healing) ─────────────────
#
# Data-page corruption does not trip CREATE TABLE IF NOT EXISTS (SQLite
# only validates pages it touches), so the opener's first failure is
# simulated — but the on-disk corruption, the salvage, the verify and
# the .bak are all real.


def test_capture_store_self_heals_on_open_error(tmp_path, monkeypatch):
    from core.cognition.capture.store import CaptureStore

    db = tmp_path / "captures.db"
    _make_db(db)
    _corrupt_last_page(db)
    assert not _quick_ok(db)
    orig_init = CaptureStore._init_db
    calls = {"n": 0}

    def flaky_init(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.DatabaseError("database disk image is malformed")
        return orig_init(self)

    monkeypatch.setattr(CaptureStore, "_init_db", flaky_init)
    store = CaptureStore(str(db))  # must not raise
    assert calls["n"] == 2  # recovered, then reopened
    assert store.stats() is not None
    assert list(tmp_path.glob("*.corrupt-*.bak"))
    assert _quick_ok(db)


def test_vector_store_self_heals_on_open_error(tmp_path, monkeypatch):
    from core.knowledge.vector_store import VectorStore

    db = tmp_path / "knowledge.db"
    _make_db(db)
    _corrupt_last_page(db)
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
    assert store.get_stats() is not None
    assert list(tmp_path.glob("*.corrupt-*.bak"))
    assert _quick_ok(db)


# ─── CLI ───────────────────────────────────────────────────────────────


def test_cli_healthy(tmp_path, capsys):
    db = tmp_path / "cli.db"
    _make_db(db)
    assert main([str(db)]) == 0
    assert '"not-corrupt"' in capsys.readouterr().out


def test_cli_usage():
    assert main([]) == 2
