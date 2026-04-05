"""Task schema for background operations.

Tasks represent async work: KB downloads, transcriptions, long-running
analysis, AI generation, etc. Each task has a lifecycle and can be
queried for status.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    READY = "ready"             # Needs human/AI interaction to continue
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    KB_DOWNLOAD = "kb_download"       # Download media (YouTube, etc.)
    KB_TRANSCRIBE = "kb_transcribe"   # Transcribe audio/video
    KB_ANALYZE = "kb_analyze"         # AI analysis of content
    RESEARCH = "research"             # Background research
    GENERATION = "generation"         # AI content/image generation
    EXPORT = "export"                 # Export to external system
    CUSTOM = "custom"


class Task(BaseModel):
    """A background task with lifecycle tracking."""
    id: str
    type: TaskType = TaskType.CUSTOM
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    department: str = ""
    agent_id: str = ""

    # Input/output
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    output_path: str = ""             # File path for output

    # Progress
    progress_percent: int = 0         # 0-100
    progress_message: str = ""

    # Timing
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""

    # Error
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3

    def start(self) -> None:
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now().isoformat()

    def complete(self, output: dict | None = None, path: str = "") -> None:
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        self.progress_percent = 100
        if output:
            self.output_data = output
        if path:
            self.output_path = path

    def fail(self, error: str) -> None:
        self.error = error
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = TaskStatus.QUEUED
            self.progress_message = f"Retry {self.retry_count}/{self.max_retries}"
        else:
            self.status = TaskStatus.FAILED

    def cancel(self) -> None:
        self.status = TaskStatus.CANCELLED

    def update_progress(self, percent: int, message: str = "") -> None:
        self.progress_percent = min(percent, 100)
        if message:
            self.progress_message = message

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        return self.status in (TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.ANALYZING)

    @property
    def duration_seconds(self) -> float | None:
        if not self.started_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at) if self.completed_at else datetime.now()
        return (end - start).total_seconds()
