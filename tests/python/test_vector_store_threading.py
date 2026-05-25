"""Tests for the PR73 v2.91.0 cross-thread SQLite fix.

Regression test for the operator-reported bug:

    SQLite objects created in a thread can only be used in that same thread

The fix opens the connection with ``check_same_thread=False`` and
serialises writes with a per-instance ``threading.Lock``. This test
constructs a VectorStore on the main thread, then exercises it from
two background workers concurrently; before PR73 the second worker
raised; after PR73 both succeed.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from core.knowledge.vector_store import VectorStore


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    return VectorStore(tmp_path / "kb.db")


def test_store_can_be_used_from_background_thread(store: VectorStore):
    """A worker thread can call index_chunks + search on a store created
    on the main thread without raising sqlite3.ProgrammingError."""
    errors: list[BaseException] = []

    def worker():
        try:
            store.index_chunks(
                texts=["chunk one", "chunk two"],
                headings=["h1", "h2"],
                source="/path/to/source.md",
            )
            store.search("chunk", top_k=2)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=10)

    assert not t.is_alive(), "worker hung"
    assert errors == [], f"worker raised: {errors!r}"


def test_concurrent_writes_do_not_corrupt(store: VectorStore):
    """Two workers writing simultaneously both complete; total chunk
    count equals the sum of what each wrote."""
    errors: list[BaseException] = []

    def writer(prefix: str):
        try:
            store.index_chunks(
                texts=[f"{prefix}-{i}" for i in range(5)],
                source=f"/{prefix}.md",
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(name,))
        for name in ("alpha", "beta", "gamma")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()

    assert errors == []
    stats = store.get_stats()
    assert stats["total_chunks"] == 15  # 3 writers × 5 chunks each


def test_main_thread_can_still_use_store_after_thread_writes(
    store: VectorStore,
):
    """Sanity check: the main thread still owns its handle after
    background work — no state is consumed."""
    errors: list[BaseException] = []

    def worker():
        try:
            store.index_chunks(texts=["bg"], source="/bg.md")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)
    assert errors == []

    store.index_chunks(texts=["main"], source="/main.md")
    assert store.get_stats()["total_chunks"] == 2


def test_check_same_thread_is_disabled(store: VectorStore):
    """Document the contract: the connection accepts cross-thread use."""
    # Simply touching the connection from another thread shouldn't raise.
    errors: list[BaseException] = []

    def worker():
        try:
            store._db.execute("SELECT 1").fetchone()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)
    assert errors == []
