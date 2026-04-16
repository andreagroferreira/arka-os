"""Memory Compression — archive old sessions, keep hot data accessible.

Hot data (last 7 days) stays uncompressed in ~/.arkaos/sessions/
Cold data (older than 7 days) gets compressed to ~/.arkaos/archive/

Compression is lossless — all JSON is preserved, just compressed with gzip.
"""

import gzip
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HOT_DAYS = 7
SESSIONS_DIR = Path.home() / ".arkaos" / "sessions"
ARCHIVE_DIR = Path.home() / ".arkaos" / "archive"


def _ensure_archive_dir() -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    return ARCHIVE_DIR


def _is_hot(session_dir: Path) -> bool:
    """Check if a session is still hot (within hot days)."""
    meta_file = session_dir / "session-meta.json"
    if not meta_file.exists():
        return False

    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        ended_at = data.get("ended_at", data.get("started_at", ""))
        if not ended_at:
            return True

        dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=HOT_DAYS)
        return dt > cutoff
    except (json.JSONDecodeError, ValueError, KeyError, OSError):
        return False


def _compress_session(session_dir: Path) -> Path:
    """Compress a session directory to archive.

    Args:
        session_dir: Path to session directory

    Returns:
        Path to compressed archive file
    """
    archive_dir = _ensure_archive_dir()
    archive_file = archive_dir / f"{session_dir.name}.tar.gz"

    if archive_file.exists():
        archive_file.unlink()

    shutil.make_archive(
        str(archive_dir / session_dir.name),
        format="gztar",
        root_dir=session_dir.parent,
        base_dir=session_dir.name,
    )

    return archive_file


def _decompress_session(archive_file: Path, target_dir: Path) -> Path:
    """Decompress a session from archive.

    Args:
        archive_file: Path to .tar.gz archive
        target_dir: Directory to extract into (should be SESSIONS_DIR)

    Returns:
        Path to decompressed session directory (target_dir / session_id)
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(archive_file, target_dir)

    import tarfile

    with tarfile.open(archive_file, "r:gz") as tf:
        names = tf.getnames()
        if names:
            session_name = names[0]
            return target_dir / session_name

    return target_dir


def compress_old_sessions() -> dict[str, Any]:
    """Compress all cold sessions to archive.

    Returns:
        Dict with counts of archived and remaining sessions
    """
    if not SESSIONS_DIR.exists():
        return {"archived": 0, "remaining": 0, "errors": []}

    archived = 0
    remaining = 0
    errors = []

    for session_dir in list(SESSIONS_DIR.iterdir()):
        if not session_dir.is_dir():
            continue

        if _is_hot(session_dir):
            remaining += 1
            continue

        try:
            archive_file = _compress_session(session_dir)
            shutil.rmtree(session_dir)
            archived += 1
        except Exception as e:
            errors.append(f"{session_dir.name}: {str(e)}")

    return {
        "archived": archived,
        "remaining": remaining,
        "errors": errors,
    }


def restore_session(session_id: str) -> Path | None:
    """Restore a session from archive.

    Args:
        session_id: Session UUID to restore

    Returns:
        Path to restored session directory, or None if not found
    """
    archive_file = ARCHIVE_DIR / f"{session_id}.tar.gz"
    if not archive_file.exists():
        return None

    target_dir = SESSIONS_DIR / session_id
    if target_dir.exists():
        return target_dir

    return _decompress_session(archive_file, SESSIONS_DIR)


def list_archived_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """List sessions in archive.

    Args:
        limit: Maximum number to return

    Returns:
        List of archived session info dicts
    """
    if not ARCHIVE_DIR.exists():
        return []

    archived = []
    for archive_file in sorted(
        ARCHIVE_DIR.glob("*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]:
        try:
            stat = archive_file.stat()
            archived.append(
                {
                    "session_id": archive_file.name[:-7],
                    "archived_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "size_bytes": stat.st_size,
                }
            )
        except OSError:
            pass

    return archived


def prune_archive(older_than_days: int = 90) -> int:
    """Delete archives older than specified days.

    Args:
        older_than_days: Delete archives older than this many days

    Returns:
        Number of archives deleted
    """
    if not ARCHIVE_DIR.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    deleted = 0

    for archive_file in list(ARCHIVE_DIR.glob("*.tar.gz")):
        try:
            mtime = datetime.fromtimestamp(archive_file.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                archive_file.unlink()
                deleted += 1
        except OSError:
            pass

    return deleted


def get_storage_stats() -> dict[str, Any]:
    """Get storage usage statistics.

    Returns:
        Dict with session counts, archive size, etc.
    """
    sessions_count = 0
    sessions_size = 0
    hot_count = 0

    if SESSIONS_DIR.exists():
        for session_dir in SESSIONS_DIR.iterdir():
            if session_dir.is_dir():
                sessions_count += 1
                if _is_hot(session_dir):
                    hot_count += 1
                sessions_size += sum(
                    f.stat().st_size for f in session_dir.rglob("*") if f.is_file()
                )

    archive_size = 0
    archive_count = 0
    if ARCHIVE_DIR.exists():
        for archive_file in ARCHIVE_DIR.glob("*.tar.gz"):
            archive_count += 1
            archive_size += archive_file.stat().st_size

    return {
        "sessions": {
            "total": sessions_count,
            "hot": hot_count,
            "cold": sessions_count - hot_count,
            "size_bytes": sessions_size,
        },
        "archive": {
            "count": archive_count,
            "size_bytes": archive_size,
        },
    }


class SessionCompressor:
    """Class-based interface for compression operations."""

    def compress_old(self) -> dict[str, Any]:
        return compress_old_sessions()

    def restore(self, session_id: str) -> Path | None:
        return restore_session(session_id)

    def list_archived(self, limit: int = 20) -> list[dict[str, Any]]:
        return list_archived_sessions(limit)

    def prune(self, older_than_days: int = 90) -> int:
        return prune_archive(older_than_days)

    def stats(self) -> dict[str, Any]:
        return get_storage_stats()
