"""SQLite self-heal (F1-D1 — memory/learning reform).

Python port of a verified claude-flow v3 pattern (recoverMemoryDatabase):
    1. confirm corruption first (``PRAGMA quick_check``) — never rewrite
       a healthy DB
    2. exclusive-writer guard (``BEGIN IMMEDIATE``) — never race a live
       writer
    3. salvage rows in rowid-range chunks into a sibling file — rows on
       unreadable pages are lost, rows on healthy pages survive; a table
       whose schema can't be recreated is skipped whole
    4. verify the rebuild BEFORE touching the original:
       ``integrity_check`` plus a non-circular row floor — a rebuild
       that lost every row of a store that demonstrably had rows, or
       less than half of any fully-countable table, is refused
    5. atomic ``os.replace`` swap, corrupt original kept as ``.bak``

Never destructive: every failure path leaves the original untouched,
and a "successful" heal that would silently empty the live store is
treated as a failure (``verify-failed``), not a success.

CLI: ``python3 -m core.shared.sqlite_recovery <db_path>``
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

_SALVAGE_CHUNK = 200  # rows fetched per rowid-range step
_MAX_SKIPS = 4096  # single-row steps past unreadable rows — bounded walk
_FLOOR_FRACTION = 0.5  # countable tables must keep at least this share


class RecoveryResult(BaseModel):
    """Outcome of a recovery attempt — reasons are honest, never blank."""

    recovered: bool = False
    reason: str = ""
    backup_path: str = ""
    rows_recovered: int = 0


@dataclass
class SalvageOutcome:
    copied: int = 0  # rows written to the rebuild
    countable_est: int = 0  # source rows across fully-countable tables
    countable_copied: int = 0  # rows copied from those same tables
    hit_errors: bool = False  # at least one unreadable range/table


def _quote(name: str) -> str:
    """Quote an SQL identifier from a possibly-hostile sqlite_master."""
    return '"' + name.replace('"', '""') + '"'


def _quick_check_ok(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("PRAGMA quick_check(1)").fetchone()
        return bool(row) and str(row[0]).lower() == "ok"
    except sqlite3.DatabaseError:
        return False  # so corrupt the check itself fails — proceed to salvage


def _count_rows(src: sqlite3.Connection, name: str) -> Optional[int]:
    """Best-effort source count; None when the table can't be scanned."""
    count_sql = f"SELECT COUNT(*) FROM {_quote(name)}"  # identifier quoted above
    try:
        return int(src.execute(count_sql).fetchone()[0])
    except sqlite3.Error:
        return None


def _copy_whole(src: sqlite3.Connection, dst: sqlite3.Connection, name: str) -> tuple[int, bool]:
    """WITHOUT ROWID fallback: all-or-nothing copy of one table."""
    select_sql = f"SELECT * FROM {_quote(name)}"  # identifier quoted above
    try:
        rows = src.execute(select_sql).fetchall()
    except sqlite3.Error:
        return 0, True
    if rows:
        marks = ",".join("?" * len(rows[0]))
        dst.executemany(f"INSERT OR IGNORE INTO {_quote(name)} VALUES ({marks})", rows)
    return len(rows), False


def _narrow_or_step(chunk: int, last: int, skips: int) -> tuple[int, int, int]:
    """Halve a failing range; once isolated, step past ONLY the bad row."""
    if chunk > 1:
        return chunk // 2, last, skips
    return 1, last + 1, skips + 1


def _walk_table(src: sqlite3.Connection, dst: sqlite3.Connection, name: str) -> tuple[int, bool]:
    """Adaptive rowid walk — one bad page loses only its own rows,
    never healthy neighbours."""
    q = _quote(name)
    table_info_sql = f"PRAGMA table_info({q})"  # identifier quoted above
    cols = [r[1] for r in dst.execute(table_info_sql).fetchall()]
    if not cols:
        return 0, True
    col_list = ",".join(["rowid"] + [_quote(c) for c in cols])
    marks = ",".join("?" * (len(cols) + 1))
    insert = f"INSERT OR IGNORE INTO {q} ({col_list}) VALUES ({marks})"
    select_sql = f"SELECT rowid,* FROM {q} WHERE rowid > ? ORDER BY rowid LIMIT ?"
    copied, errors, skips, last, chunk = 0, False, 0, 0, _SALVAGE_CHUNK
    while skips < _MAX_SKIPS:
        try:
            rows = src.execute(select_sql, (last, chunk)).fetchall()
        except sqlite3.Error as exc:
            if isinstance(exc, sqlite3.OperationalError) and "rowid" in str(exc).lower():
                return _copy_whole(src, dst, name)  # WITHOUT ROWID table
            errors = True
            chunk, last, skips = _narrow_or_step(chunk, last, skips)
            continue
        if not rows:
            break
        dst.executemany(insert, rows)
        copied, last, chunk = copied + len(rows), rows[-1][0], _SALVAGE_CHUNK
    return copied, errors


def _salvage_into(src: sqlite3.Connection, tmp_path: Path) -> SalvageOutcome:
    """Copy schema + readable rows into ``tmp_path`` (table-level stats)."""
    objects = src.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    out = SalvageOutcome()
    dst = sqlite3.connect(tmp_path)
    try:
        for kind, name, sql in objects:
            if kind != "table":
                continue
            try:
                dst.execute(sql)
            except sqlite3.Error:
                out.hit_errors = True
                continue  # untranslatable table def — skip whole table
            copied, errors = _walk_table(src, dst, name)
            out.copied += copied
            out.hit_errors = out.hit_errors or errors
            est = _count_rows(src, name)
            if est is not None:
                out.countable_est += est
                out.countable_copied += copied
        for kind, _name, sql in objects:
            if kind == "table":
                continue
            try:
                dst.execute(sql)
            except sqlite3.Error:
                pass  # an index over corrupt data — non-fatal
        dst.commit()
        return out
    finally:
        dst.close()


def _floor_ok(out: SalvageOutcome) -> bool:
    """Refuse a rebuild that silently emptied or gutted the store."""
    had_rows = out.countable_est > 0 or out.hit_errors
    if out.copied == 0 and had_rows:
        return False
    if out.countable_est > 0:
        return out.countable_copied >= int(out.countable_est * _FLOOR_FRACTION)
    return True


def _rebuilt_is_healthy(tmp_path: Path, out: SalvageOutcome) -> bool:
    """Verify BEFORE touching the original: integrity ok + row floor."""
    if not _floor_ok(out):
        return False
    try:
        check = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        try:
            row = check.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and str(row[0]).lower() == "ok"
        finally:
            check.close()
    except sqlite3.Error:
        return False


def _swap_in(db: Path, tmp: Path, bak: Path, copied: int) -> RecoveryResult:
    """Back up the corrupt original, then atomically install the rebuild."""
    shutil.copyfile(db, bak)
    os.replace(tmp, db)
    for suffix in ("-wal", "-shm"):
        Path(f"{db}{suffix}").unlink(missing_ok=True)
    return RecoveryResult(recovered=True, backup_path=str(bak), rows_recovered=copied)


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
            outcome = _salvage_into(src, tmp)
        except sqlite3.Error:
            tmp.unlink(missing_ok=True)
            return RecoveryResult(reason="unreadable")
        finally:
            try:
                src.execute("ROLLBACK")
            except sqlite3.Error:
                pass
    finally:
        src.close()
    if not _rebuilt_is_healthy(tmp, outcome):
        tmp.unlink(missing_ok=True)
        return RecoveryResult(reason="verify-failed")
    return _swap_in(db, tmp, bak, outcome.copied)


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
