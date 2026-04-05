"""Tests for the Background Task system."""

import pytest
import tempfile
from pathlib import Path

from core.tasks.schema import Task, TaskStatus, TaskType
from core.tasks.manager import TaskManager


class TestTaskSchema:
    def test_create_task(self):
        task = Task(id="t1", title="Download video", type=TaskType.KB_DOWNLOAD)
        assert task.status == TaskStatus.QUEUED
        assert task.progress_percent == 0

    def test_start_task(self):
        task = Task(id="t1", title="Test")
        task.start()
        assert task.status == TaskStatus.PROCESSING
        assert task.started_at

    def test_complete_task(self):
        task = Task(id="t1", title="Test")
        task.start()
        task.complete(output={"result": "done"}, path="/output/file.md")
        assert task.status == TaskStatus.COMPLETED
        assert task.progress_percent == 100
        assert task.output_data["result"] == "done"
        assert task.output_path == "/output/file.md"

    def test_fail_with_retry(self):
        task = Task(id="t1", title="Test", max_retries=3)
        task.start()
        task.fail("Network error")
        assert task.status == TaskStatus.QUEUED  # Retries
        assert task.retry_count == 1

    def test_fail_exhausted_retries(self):
        task = Task(id="t1", title="Test", max_retries=1)
        task.start()
        task.fail("Error 1")
        assert task.status == TaskStatus.QUEUED  # 1st retry
        task.start()
        task.fail("Error 2")
        assert task.status == TaskStatus.FAILED  # Exhausted

    def test_cancel(self):
        task = Task(id="t1", title="Test")
        task.cancel()
        assert task.status == TaskStatus.CANCELLED

    def test_update_progress(self):
        task = Task(id="t1", title="Test")
        task.start()
        task.update_progress(50, "Halfway there")
        assert task.progress_percent == 50
        assert task.progress_message == "Halfway there"

    def test_progress_capped_at_100(self):
        task = Task(id="t1", title="Test")
        task.update_progress(150)
        assert task.progress_percent == 100

    def test_is_terminal(self):
        task = Task(id="t1", title="Test")
        assert not task.is_terminal
        task.complete()
        assert task.is_terminal

    def test_is_active(self):
        task = Task(id="t1", title="Test")
        assert not task.is_active
        task.start()
        assert task.is_active

    def test_duration(self):
        task = Task(id="t1", title="Test")
        assert task.duration_seconds is None
        task.start()
        task.complete()
        assert task.duration_seconds is not None
        assert task.duration_seconds >= 0


class TestTaskManager:
    def test_create_task(self):
        mgr = TaskManager()
        task = mgr.create("Download video", TaskType.KB_DOWNLOAD)
        assert task.id == "task-0001"
        assert task.status == TaskStatus.QUEUED

    def test_incremental_ids(self):
        mgr = TaskManager()
        t1 = mgr.create("Task 1")
        t2 = mgr.create("Task 2")
        assert t1.id == "task-0001"
        assert t2.id == "task-0002"

    def test_get_task(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        assert mgr.get(task.id) is not None
        assert mgr.get("nonexistent") is None

    def test_start_task(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        assert mgr.start(task.id)
        assert task.status == TaskStatus.PROCESSING

    def test_complete_task(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        mgr.start(task.id)
        mgr.complete(task.id, output={"key": "value"})
        assert task.status == TaskStatus.COMPLETED

    def test_fail_task(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        mgr.start(task.id)
        mgr.fail(task.id, "Something broke")
        assert task.error == "Something broke"

    def test_cancel_task(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        assert mgr.cancel(task.id)
        assert task.status == TaskStatus.CANCELLED

    def test_cannot_cancel_completed(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        mgr.start(task.id)
        mgr.complete(task.id)
        assert not mgr.cancel(task.id)

    def test_list_all(self):
        mgr = TaskManager()
        mgr.create("T1")
        mgr.create("T2")
        mgr.create("T3")
        assert len(mgr.list_all()) == 3

    def test_list_by_status(self):
        mgr = TaskManager()
        t1 = mgr.create("T1")
        t2 = mgr.create("T2")
        mgr.start(t1.id)
        assert len(mgr.list_all(TaskStatus.QUEUED)) == 1
        assert len(mgr.list_active()) == 1

    def test_summary(self):
        mgr = TaskManager()
        mgr.create("T1")
        t2 = mgr.create("T2")
        mgr.start(t2.id)
        s = mgr.summary()
        assert s["total"] == 2
        assert s["queued"] == 1
        assert s["active"] == 1

    def test_cleanup_completed(self):
        mgr = TaskManager()
        for i in range(10):
            t = mgr.create(f"Task {i}")
            mgr.start(t.id)
            mgr.complete(t.id)
        removed = mgr.cleanup_completed(keep_last=5)
        assert removed == 5
        assert len(mgr.list_all()) == 5

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        # Create and save
        mgr1 = TaskManager(storage_path=path)
        t = mgr1.create("Persistent task", TaskType.KB_DOWNLOAD)
        mgr1.start(t.id)
        mgr1.update_progress(t.id, 50, "Halfway")

        # Load in new manager
        mgr2 = TaskManager(storage_path=path)
        loaded = mgr2.get(t.id)
        assert loaded is not None
        assert loaded.title == "Persistent task"
        assert loaded.progress_percent == 50

        Path(path).unlink()

    def test_update_progress(self):
        mgr = TaskManager()
        task = mgr.create("Test")
        mgr.start(task.id)
        mgr.update_progress(task.id, 75, "Almost done")
        assert task.progress_percent == 75
