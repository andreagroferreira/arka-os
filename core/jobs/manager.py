"""SQLite-based job queue for persistent task tracking.

Cross-platform (Mac, Linux, Windows). Thread-safe. Survives restarts.
"""

import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Job:
    id: str
    type: str = ""            # youtube, pdf, audio, web, markdown, kb_index
    source: str = ""          # URL or file path
    title: str = ""
    status: str = "queued"    # queued, processing, downloading, transcribing, embedding, completed, failed, cancelled
    progress: int = 0         # 0-100
    message: str = ""         # Current step description
    chunks_created: int = 0
    error: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class JobManager:
    """SQLite-backed job queue. Thread-safe for concurrent reads."""

    def __init__(self, db_path: str | Path = ""):
        self._db_path = str(db_path) if db_path else str(Path.home() / ".arkaos" / "jobs.db")
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    progress INTEGER DEFAULT 0,
                    message TEXT DEFAULT '',
                    chunks_created INTEGER DEFAULT 0,
                    error TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    started_at TEXT DEFAULT '',
                    completed_at TEXT DEFAULT ''
                )
            """)

    def create(self, source: str, source_type: str, title: str = "") -> Job:
        job = Job(
            id=f"job-{uuid.uuid4().hex[:8]}",
            type=source_type,
            source=source,
            title=title or f"{source_type}: {source[:60]}",
            status="queued",
            created_at=datetime.now().isoformat(),
        )
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO jobs (id, type, source, title, status, progress, message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (job.id, job.type, job.source, job.title, job.status, 0, "Queued", job.created_at),
            )
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            return Job(**dict(row))

    def update_progress(self, job_id: str, progress: int, message: str, status: str = "processing") -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET progress = ?, message = ?, status = ? WHERE id = ?",
                (progress, message, status, job_id),
            )

    def start(self, job_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'processing', started_at = ? WHERE id = ?",
                (datetime.now().isoformat(), job_id),
            )

    def complete(self, job_id: str, chunks_created: int = 0) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'completed', progress = 100, message = 'Done', chunks_created = ?, completed_at = ? WHERE id = ?",
                (chunks_created, datetime.now().isoformat(), job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
                (error, datetime.now().isoformat(), job_id),
            )

    def cancel(self, job_id: str) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE jobs SET status = 'cancelled', completed_at = ? WHERE id = ? AND status = 'queued'",
                (datetime.now().isoformat(), job_id),
            )
            return result.rowcount > 0

    def list_all(self, limit: int = 50) -> list[Job]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [Job(**dict(r)) for r in rows]

    def list_active(self) -> list[Job]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status IN ('queued', 'processing', 'downloading', 'transcribing', 'embedding') ORDER BY created_at ASC"
            ).fetchall()
            return [Job(**dict(r)) for r in rows]

    def list_by_status(self, status: str, limit: int = 50) -> list[Job]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)
            ).fetchall()
            return [Job(**dict(r)) for r in rows]

    def summary(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'processing', 'downloading', 'transcribing', 'embedding')").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'failed'").fetchone()[0]
            total_chunks = conn.execute("SELECT COALESCE(SUM(chunks_created), 0) FROM jobs WHERE status = 'completed'").fetchone()[0]
            return {
                "total": total,
                "active": active,
                "completed": completed,
                "failed": failed,
                "total_chunks": total_chunks,
            }

    def clear_completed(self, keep_last: int = 20) -> int:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs WHERE status IN ('completed', 'failed', 'cancelled') ORDER BY completed_at DESC"
            ).fetchall()
            to_delete = [r["id"] for r in rows[keep_last:]]
            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", to_delete)
            return len(to_delete)
