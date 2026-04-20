"""Tests for core.jobs.auto_doc_worker — Task #7 async queue."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core.jobs import auto_doc_worker as worker


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def queue(tmp_path) -> Path:
    root = tmp_path / "queue"
    for sub in ("pending", "processing", "completed", "failed"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture
def patch_execute(monkeypatch):
    """Replace the heavy `_execute` with a deterministic stub."""
    calls: list[dict] = []

    def fake(payload):
        calls.append(payload)
        return ["/vault/note.md"]

    monkeypatch.setattr(worker, "_execute", fake)
    return calls


# ─── enqueue_job ───────────────────────────────────────────────────────


def test_enqueue_job_creates_file(queue):
    job_id = worker.enqueue_job("sess-1", "/t.jsonl", "APPROVED", queue_root=queue)
    files = list((queue / "pending").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["job_id"] == job_id
    assert payload["session_id"] == "sess-1"
    assert payload["transcript_path"] == "/t.jsonl"
    assert payload["qg_verdict"] == "APPROVED"


def test_enqueue_job_returns_unique_id(queue):
    a = worker.enqueue_job("sess-1", "/t.jsonl", "APPROVED", queue_root=queue)
    b = worker.enqueue_job("sess-1", "/t.jsonl", "APPROVED", queue_root=queue)
    assert a != b
    assert len(list((queue / "pending").glob("*.json"))) == 2


def test_enqueue_job_sanitizes_bad_session_id(queue):
    worker.enqueue_job("../evil", "/t.jsonl", "APPROVED", queue_root=queue)
    payload = json.loads(next((queue / "pending").iterdir()).read_text(encoding="utf-8"))
    assert payload["session_id"] == "unknown"


# ─── process_pending_jobs ──────────────────────────────────────────────


def test_process_pending_jobs_respects_max(queue, patch_execute):
    for i in range(5):
        worker.enqueue_job(f"s{i}", "/t.jsonl", "APPROVED", queue_root=queue)
    results = worker.process_pending_jobs(max_jobs=2, queue_root=queue)
    assert len(results) == 2
    # Remaining 3 must still be pending.
    assert len(list((queue / "pending").glob("*.json"))) == 3


def test_run_single_job_success_moves_to_completed(queue, patch_execute):
    worker.enqueue_job("sess-ok", "/t.jsonl", "APPROVED", queue_root=queue)
    results = worker.process_pending_jobs(max_jobs=1, queue_root=queue)
    assert results[0]["status"] == "completed"
    assert len(list((queue / "completed").glob("*.json"))) == 1
    assert len(list((queue / "pending").glob("*.json"))) == 0
    done = json.loads(next((queue / "completed").iterdir()).read_text(encoding="utf-8"))
    assert done["written_paths"] == ["/vault/note.md"]


def test_run_single_job_failure_moves_to_failed_after_3_retries(
    queue, monkeypatch
):
    def boom(_payload):
        raise RuntimeError("always fails")

    monkeypatch.setattr(worker, "_execute", boom)
    worker.enqueue_job("sess-fail", "/t.jsonl", "APPROVED", queue_root=queue)

    for _ in range(worker.MAX_ATTEMPTS):
        worker.process_pending_jobs(max_jobs=10, queue_root=queue)

    assert len(list((queue / "failed").glob("*.json"))) == 1
    assert len(list((queue / "pending").glob("*.json"))) == 0
    failed = json.loads(next((queue / "failed").iterdir()).read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert "always fails" in failed["error"]


def test_atomic_move_between_states(queue, patch_execute):
    worker.enqueue_job("sess", "/t.jsonl", "APPROVED", queue_root=queue)
    pending = next((queue / "pending").iterdir())
    claimed = worker._claim(pending, queue)
    assert claimed is not None
    assert claimed.parent.name == "processing"
    assert not pending.exists()


def test_concurrent_workers_race_safe(queue, patch_execute):
    # Enqueue many jobs, run two "workers" in parallel, assert no duplicate processing.
    for i in range(20):
        worker.enqueue_job(f"s{i}", "/t.jsonl", "APPROVED", queue_root=queue)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker.process_pending_jobs, 20, queue) for _ in range(2)
        ]
        for fut in futures:
            fut.result()
    completed = len(list((queue / "completed").glob("*.json")))
    assert completed == 20
    assert len(list((queue / "pending").glob("*.json"))) == 0
    assert len(list((queue / "processing").glob("*.json"))) == 0


def test_malformed_job_file_moves_to_failed(queue):
    bad = queue / "pending" / "bad.json"
    bad.write_text("{not-valid-json", encoding="utf-8")
    results = worker.process_pending_jobs(max_jobs=5, queue_root=queue)
    assert results and results[0]["status"] == "failed"
    assert len(list((queue / "failed").glob("*.json"))) == 1


def test_empty_queue_returns_no_results(queue):
    assert worker.process_pending_jobs(max_jobs=5, queue_root=queue) == []


# ─── CLI ───────────────────────────────────────────────────────────────


def test_worker_cli_single_pass(queue, monkeypatch, capsys, patch_execute):
    monkeypatch.setattr(worker, "_queue_root", lambda: queue)
    worker.enqueue_job("sess", "/t.jsonl", "APPROVED", queue_root=queue)
    rc = worker.main(["--once", "--max-jobs", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"status": "completed"' in out


def test_worker_cli_handles_empty_queue(queue, monkeypatch, capsys):
    monkeypatch.setattr(worker, "_queue_root", lambda: queue)
    rc = worker.main(["--once"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out == ""


# ─── Extra robustness ─────────────────────────────────────────────────


def test_run_single_job_transient_retry_goes_back_to_pending(queue, monkeypatch):
    calls = {"n": 0}

    def sometimes(_payload):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("blip")
        return ["/vault/note.md"]

    monkeypatch.setattr(worker, "_execute", sometimes)
    worker.enqueue_job("sess", "/t.jsonl", "APPROVED", queue_root=queue)

    # First pass fails, job returns to pending.
    results = worker.process_pending_jobs(max_jobs=1, queue_root=queue)
    assert results[0]["status"] == "retry"
    assert len(list((queue / "pending").glob("*.json"))) == 1

    # Second pass succeeds.
    results = worker.process_pending_jobs(max_jobs=1, queue_root=queue)
    assert results[0]["status"] == "completed"
    assert len(list((queue / "completed").glob("*.json"))) == 1


def test_queue_root_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom-queue"
    monkeypatch.setenv("ARKA_AUTO_DOC_QUEUE", str(custom))
    job_id = worker.enqueue_job("sess", "/t.jsonl", "APPROVED")
    assert (custom / "pending" / f"{job_id}.json").exists()


def test_vault_path_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_VAULT", str(tmp_path / "vault"))
    assert worker._vault_path() == tmp_path / "vault"


def test_queue_root_default(monkeypatch):
    monkeypatch.delenv("ARKA_AUTO_DOC_QUEUE", raising=False)
    assert worker._queue_root().name == "auto-doc"


def test_vault_path_default(monkeypatch):
    monkeypatch.delenv("ARKAOS_VAULT", raising=False)
    assert worker._vault_path().name == "Personal"


def test_claim_returns_none_for_vanished_file(queue):
    ghost = queue / "pending" / "ghost.json"
    assert worker._claim(ghost, queue) is None


def test_safe_read_payload_from_corrupt_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{corrupt", encoding="utf-8")
    info = worker._safe_read_payload(bad)
    assert info["job_id"] == "bad"


def test_execute_delegates_to_documentor(monkeypatch, tmp_path):
    called = {}

    def fake(transcript, session_id, vault, verdict):
        called["transcript"] = transcript
        called["session_id"] = session_id
        called["verdict"] = verdict
        return [tmp_path / "note.md"]

    import core.cognition.auto_documentor as adoc
    monkeypatch.setattr(adoc, "document_session", fake)
    paths = worker._execute({
        "transcript_path": "/tmp/t.jsonl",
        "session_id": "sid",
        "qg_verdict": "APPROVED",
    })
    assert paths == [str(tmp_path / "note.md")]
    assert called["session_id"] == "sid"
