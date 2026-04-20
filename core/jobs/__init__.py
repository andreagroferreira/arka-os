"""Job queue — SQLite tracker + filesystem-backed auto-doc worker."""

from core.jobs.manager import Job, JobManager
from core.jobs.auto_doc_worker import (
    enqueue_job,
    process_pending_jobs,
    run_single_job,
)

__all__ = [
    "Job",
    "JobManager",
    "enqueue_job",
    "process_pending_jobs",
    "run_single_job",
]
