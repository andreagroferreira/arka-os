"""Async consumer for auto-doc jobs. Never blocks Stop hook.

Queue layout under `~/.arkaos/jobs/auto-doc/`:

    pending/     — job files enqueued by Stop hook
    processing/  — jobs currently being handled
    completed/   — jobs finished successfully
    failed/      — jobs that exhausted retries or could not be parsed

Each job is a JSON file:

    {
      "job_id": "<uuid>",
      "session_id": "<safe id>",
      "transcript_path": "/abs/path/to/transcript.jsonl",
      "qg_verdict": "APPROVED",
      "attempts": 0,
      "enqueued_at": "ISO-8601"
    }

All state transitions are atomic via `os.replace`. Concurrent workers
are race-safe: the first `os.replace` into `processing/` wins, and any
second worker that tries to claim the same job will raise and skip it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MAX_ATTEMPTS = 3
SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_QUEUE_SUBDIRS = ("pending", "processing", "completed", "failed")


def _queue_root() -> Path:
    override = os.environ.get("ARKA_AUTO_DOC_QUEUE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".arkaos" / "jobs" / "auto-doc"


def _vault_path() -> Path:
    override = os.environ.get("ARKAOS_VAULT", "").strip()
    if override:
        return Path(override)
    return Path.home() / "Documents" / "Personal"


def _ensure_queue(root: Path) -> None:
    for sub in _QUEUE_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Enqueue ───────────────────────────────────────────────────────────


def enqueue_job(
    session_id: str,
    transcript_path: str,
    qg_verdict: str,
    queue_root: Optional[Path] = None,
) -> str:
    """Write a pending job file. Returns the job id."""
    root = queue_root or _queue_root()
    _ensure_queue(root)
    safe = session_id if SAFE_SESSION_ID_RE.match(session_id or "") else "unknown"
    job_id = f"{int(time.time())}-{uuid.uuid4().hex[:12]}"
    payload = {
        "job_id": job_id,
        "session_id": safe,
        "transcript_path": str(transcript_path or ""),
        "qg_verdict": qg_verdict or "",
        "attempts": 0,
        "enqueued_at": _now_iso(),
    }
    dest = root / "pending" / f"{job_id}.json"
    tmp = dest.with_suffix(dest.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, dest)
    return job_id


# ─── Worker loop ───────────────────────────────────────────────────────


def process_pending_jobs(
    max_jobs: int = 10,
    queue_root: Optional[Path] = None,
) -> list[dict]:
    """Process up to `max_jobs` pending jobs. Returns per-job result dicts."""
    root = queue_root or _queue_root()
    _ensure_queue(root)
    results: list[dict] = []
    pending = sorted((root / "pending").glob("*.json"))
    for job_file in pending[:max_jobs]:
        claimed = _claim(job_file, root)
        if claimed is None:
            continue
        results.append(run_single_job(claimed, root))
    return results


def _claim(job_file: Path, root: Path) -> Optional[Path]:
    target = root / "processing" / job_file.name
    try:
        os.replace(job_file, target)
        return target
    except FileNotFoundError:
        return None
    except OSError:
        return None


def run_single_job(job_path: Path, queue_root: Optional[Path] = None) -> dict:
    """Process one job end-to-end. Moves to completed/ or failed/."""
    root = queue_root or _queue_root()
    _ensure_queue(root)
    try:
        payload = json.loads(job_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload not dict")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _move_to_failed(job_path, root, f"unreadable:{exc}")
    payload["attempts"] = int(payload.get("attempts") or 0) + 1
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        written = _execute(payload)
    except Exception as exc:
        return _handle_retry(job_path, payload, root, str(exc))
    return _move_to_completed(job_path, root, payload, written)


def _execute(payload: dict) -> list[str]:
    from core.cognition.auto_documentor import document_session
    transcript = Path(payload.get("transcript_path") or "")
    session_id = str(payload.get("session_id") or "")
    verdict = str(payload.get("qg_verdict") or "")
    vault = _vault_path()
    paths = document_session(transcript, session_id, vault, verdict)
    return [str(p) for p in paths]


def _handle_retry(
    job_path: Path, payload: dict, root: Path, error: str
) -> dict:
    attempts = int(payload.get("attempts") or 0)
    if attempts >= MAX_ATTEMPTS:
        return _move_to_failed(job_path, root, error)
    target = root / "pending" / job_path.name
    try:
        os.replace(job_path, target)
    except OSError:
        return _move_to_failed(job_path, root, error)
    return {
        "job_id": payload.get("job_id"),
        "status": "retry",
        "attempts": attempts,
        "error": error,
    }


def _move_to_completed(
    job_path: Path, root: Path, payload: dict, written: list[str]
) -> dict:
    payload["completed_at"] = _now_iso()
    payload["written_paths"] = written
    payload["status"] = "completed"
    target = root / "completed" / job_path.name
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        os.replace(job_path, target)
    except OSError:
        pass
    return {
        "job_id": payload.get("job_id"),
        "status": "completed",
        "written": written,
    }


def _move_to_failed(job_path: Path, root: Path, error: str) -> dict:
    target = root / "failed" / job_path.name
    info = _safe_read_payload(job_path)
    info["status"] = "failed"
    info["error"] = error
    info["failed_at"] = _now_iso()
    try:
        job_path.write_text(json.dumps(info), encoding="utf-8")
    except OSError:
        pass
    try:
        os.replace(job_path, target)
    except OSError:
        try:
            job_path.unlink()
        except OSError:
            pass
    return {
        "job_id": info.get("job_id"),
        "status": "failed",
        "error": error,
    }


def _safe_read_payload(job_path: Path) -> dict:
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return {"job_id": job_path.stem}


# ─── CLI ───────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto_doc_worker")
    parser.add_argument("--once", action="store_true",
                        help="Single pass, process available jobs and exit.")
    parser.add_argument("--max-jobs", type=int, default=10,
                        help="Cap on jobs per pass.")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds to sleep between passes when daemonised.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    results = process_pending_jobs(max_jobs=args.max_jobs)
    for r in results:
        print(json.dumps(r), flush=True)
    if args.once:
        return 0
    while True:
        time.sleep(max(0.1, float(args.interval)))
        for r in process_pending_jobs(max_jobs=args.max_jobs):
            print(json.dumps(r), flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
