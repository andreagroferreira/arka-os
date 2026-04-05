"""Task manager — queue, track, and manage background tasks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.tasks.schema import Task, TaskStatus, TaskType


class TaskManager:
    """Manages background task lifecycle.

    Tasks are stored in memory and optionally persisted to a JSON file
    for cross-session recovery.
    """

    def __init__(self, storage_path: str | Path = "") -> None:
        self._tasks: dict[str, Task] = {}
        self._counter: int = 0
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path and self._storage_path.exists():
            self._load()

    def create(
        self,
        title: str,
        task_type: TaskType = TaskType.CUSTOM,
        description: str = "",
        department: str = "",
        agent_id: str = "",
        input_data: dict | None = None,
    ) -> Task:
        """Create and queue a new task."""
        self._counter += 1
        task_id = f"task-{self._counter:04d}"

        task = Task(
            id=task_id,
            type=task_type,
            title=title,
            description=description,
            status=TaskStatus.QUEUED,
            department=department,
            agent_id=agent_id,
            input_data=input_data or {},
            created_at=datetime.now().isoformat(),
        )

        self._tasks[task_id] = task
        self._save()
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def start(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.is_terminal:
            return False
        task.start()
        self._save()
        return True

    def complete(self, task_id: str, output: dict | None = None, path: str = "") -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.complete(output, path)
        self._save()
        return True

    def fail(self, task_id: str, error: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.fail(error)
        self._save()
        return True

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.is_terminal:
            return False
        task.cancel()
        self._save()
        return True

    def update_progress(self, task_id: str, percent: int, message: str = "") -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.update_progress(percent, message)
        self._save()
        return True

    def list_all(self, status: Optional[TaskStatus] = None) -> list[Task]:
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def list_active(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.is_active]

    def list_queued(self) -> list[Task]:
        return self.list_all(TaskStatus.QUEUED)

    def cleanup_completed(self, keep_last: int = 50) -> int:
        """Remove old completed tasks, keeping the most recent."""
        completed = [t for t in self._tasks.values() if t.is_terminal]
        completed.sort(key=lambda t: t.completed_at or t.created_at, reverse=True)
        to_remove = completed[keep_last:]
        for task in to_remove:
            del self._tasks[task.id]
        if to_remove:
            self._save()
        return len(to_remove)

    def summary(self) -> dict:
        by_status: dict[str, int] = {}
        for task in self._tasks.values():
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
        return {
            "total": len(self._tasks),
            "by_status": by_status,
            "active": len(self.list_active()),
            "queued": len(self.list_queued()),
        }

    def _save(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "counter": self._counter,
            "tasks": {tid: t.model_dump(mode="json") for tid, t in self._tasks.items()},
        }
        with open(self._storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        content = self._storage_path.read_text().strip()
        if not content:
            return
        data = json.loads(content)
        self._counter = data.get("counter", 0)
        for tid, tdata in data.get("tasks", {}).items():
            self._tasks[tid] = Task.model_validate(tdata)
