"""SQLite self-heal (F1-D1 — memory/learning reform).

Python port of a verified claude-flow v3 pattern (recoverMemoryDatabase):
    1. confirm corruption first (``PRAGMA quick_check``) — never rewrite
       a healthy DB
    2. exclusive-writer guard (``BEGIN IMMEDIATE``) — never race a live
       writer
    3. salvage schema + rows table-by-table into a sibling file,
       skipping unreadable pages
    4. verify the rebuild (``integrity_check`` + row-count floor)
       BEFORE touching the original
    5. atomic ``os.replace`` swap, corrupt original kept as ``.bak``

Never destructive: every failure path leaves the original untouched.

CLI: ``python3 -m core.shared.sqlite_recovery <db_path>``
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

from pydantic import BaseModel


class RecoveryResult(BaseModel):
    """Outcome of a recovery attempt — reasons are honest, never blank."""

    recovered: bool = False
    reason: str = ""
    backup_path: str = ""
    rows_recovered: int = 0


def _quick_check_ok(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("PRAGMA quick_check(1)").fetchone()
        return bool(row) and str(row[0]).lower() == "ok"
    except sqlite3.DatabaseError:
        return False  # so corrupt the check itself fails — proceed to salvage


def _salvage_into(src: sqlite3.Connection, tmp_path: Path) -> tuple[int, int]:
    """Copy schema + readable rows into ``tmp_path``; returns (dst, src) rows."""
    objects = src.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tables = [o for o in objects if o[0] == "table"]
    dst = sqlite3.connect(tmp_path)
    try:
        copied = 0
        readable = 0
        for _, name, sql in tables:
            try:
                dst.execute(sql)
            except sqlite3.Error:
                continue  # untranslatable table def — skip whole table
            try:
                rows = src.execute(f'SELECT * FROM "{name}"').fetchall()
                readable += len(rows)
                if rows:
                    marks = ",".join("?" * len(rows[0]))
                    dst.executemany(
                        f'INSERT OR IGNORE INTO "{name}" VALUES ({marks})', rows
                    )
                    copied += len(rows)
            except sqlite3.Error:
                continue  # unreadable data pages — skip, never fabricate
        for kind, _, sql in objects:
            if kind != "table":
                try:
                    dst.execute(sql)
                except sqlite3.Error:
                    pass  # an index over corrupt data — non-fatal
        dst.commit()
        return copied, readable
    finally:
        dst.close()


def _rebuilt_is_healthy(tmp_path: Path, floor: int) -> bool:
    """Verify BEFORE touching the original: integrity ok + row floor."""
    try:
        check = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        try:
            row = check.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                return False
            total = 0
            names = check.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for (name,) in names:
                total += check.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            return total >= floor
        finally:
            check.close()
    except sqlite3.Error:
        return False


def recover(db_path: str | Path) -> RecoveryResult:
    """Attempt in-place recovery of a corrupt SQLite file (see module doc)."""
    db = Path(db_path)
    if not db.is_file():
        return RecoveryResult(reason="no-db")
    ts = int(time.time() * 1000)
    tmp = db.with_name(f"{db.name}.recovering-{ts}")
    bak = db.with_name(f"{db.name}.corrupt-{ts}.bak")
    src = sqlite3.connect(db, timeout=1.5, isolation_level=None)
    try:
        if _quick_check_ok(src):
            return RecoveryResult(reason="not-corrupt")
        try:
            src.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return RecoveryResult(reason="writer-active")
        except sqlite3.DatabaseError:
            # Not even lockable (e.g. "file is not a database") — nothing
            # sqlite3 can salvage; leave the original byte-for-byte intact.
            return RecoveryResult(reason="unreadable")
        try:
            copied, readable = _salvage_into(src, tmp)
        except sqlite3.Error:
            tmp.unlink(missing_ok=True)
            return RecoveryResult(reason="unreadable")
        finally:
            try:
                src.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        if not _rebuilt_is_healthy(tmp, floor=readable):
            tmp.unlink(missing_ok=True)
            return RecoveryResult(reason="verify-failed")
        shutil.copyfile(db, bak)
        os.replace(tmp, db)
        for suffix in ("-wal", "-shm"):
            Path(f"{db}{suffix}").unlink(missing_ok=True)
        return RecoveryResult(
            recovered=True, backup_path=str(bak), rows_recovered=copied
        )
    finally:
        src.close()


def open_with_recovery(db_path: str | Path, opener):
    """Run ``opener()``; on DatabaseError recover ONCE and retry.

    ``opener`` is a zero-arg callable that opens/initialises the store.
    A second failure propagates — callers keep their own degraded paths.
    """
    try:
        return opener()
    except sqlite3.DatabaseError:
        result = recover(db_path)
        if not result.recovered:
            raise
        return opener()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python3 -m core.shared.sqlite_recovery <db_path>")
        return 2
    result = recover(args[0])
    print(json.dumps(result.model_dump()))
    return 0 if result.recovered or result.reason == "not-corrupt" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
