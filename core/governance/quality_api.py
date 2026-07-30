"""Quality Gate API — submit deliverables, query status, record verdicts.

Provides a simple programmatic interface for the Quality Gate system:
- submit() — submit a deliverable for review
- query() — check status of a submission
- verdict() — record a reviewer's verdict
- list_pending() — get all pending reviews
"""

import json
from datetime import UTC
from pathlib import Path
from typing import Any

from core.governance.quality_router import (
    DeliverableType,
    QualityRouter,
)

_STATE_DIR = Path.home() / ".arkaos" / "quality-gate"
_QUEUE_FILE = _STATE_DIR / "queue.json"
_WORKFLOWS_FILE = _STATE_DIR / "workflows.json"


def _ensure_state_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_queue() -> list[dict]:
    _ensure_state_dir()
    if not _QUEUE_FILE.exists():
        return []
    try:
        return json.loads(_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_queue(queue: list[dict]) -> None:
    _ensure_state_dir()
    _QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def _load_workflows() -> list[dict]:
    _ensure_state_dir()
    if not _WORKFLOWS_FILE.exists():
        return []
    try:
        return json.loads(_WORKFLOWS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_workflows(workflows: list[dict]) -> None:
    _ensure_state_dir()
    _WORKFLOWS_FILE.write_text(json.dumps(workflows, indent=2))


def submit(
    title: str,
    description: str,
    deliverable_type: str | None = None,
    submitter: str = "unknown",
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Submit a deliverable for Quality Gate review.

    Args:
        title: Deliverable title
        description: Brief description
        deliverable_type: Type as string (auto-detected if None)
        submitter: Agent ID of submitter
        metadata: Additional context

    Returns:
        Dict with submission_id, reviewers, priority, and estimated_sla
    """
    detype = DeliverableType(deliverable_type) if deliverable_type else None

    router = QualityRouter()
    assignment = router.route(title, description, detype, submitter, metadata)

    queue = _load_queue()
    queue.append(
        {
            "id": assignment.id,
            "title": assignment.title,
            "deliverable_type": assignment.deliverable_type.value,
            "submitter": assignment.submitter,
            "reviewers": [r.value for r in assignment.reviewers],
            "priority": assignment.priority.value,
            "status": assignment.status,
            "submitted_at": assignment.submitted_at,
            "sla_due": assignment.sla_due,
        }
    )
    _save_queue(queue)

    return {
        "submission_id": assignment.id,
        "reviewers": [r.value for r in assignment.reviewers],
        "priority": assignment.priority.value,
        "estimated_sla": assignment.sla_due,
        "deliverable_type": assignment.deliverable_type.value,
    }


def query(submission_id: str) -> dict[str, Any] | None:
    """Query the status of a submission.

    Args:
        submission_id: ID returned from submit()

    Returns:
        Status dict or None if not found
    """
    queue = _load_queue()
    for item in queue:
        if item["id"] == submission_id:
            return item

    workflows = _load_workflows()
    for wf in workflows:
        if wf["id"] == submission_id:
            return wf

    return None


def record_verdict(
    submission_id: str,
    reviewer: str,
    verdict: str,
    feedback: str = "",
    flagged_rules: list[str] | None = None,
) -> bool:
    """Record a reviewer's verdict for a submission.

    .. deprecated:: 4.44.0 (PR-B5)
        Writes an unguarded label: no ledger artifact, no digest, no
        aggregate guard. Use ``core.evals.record_cli``: ``--kind qg``
        passes ``aggregate_guard.check_aggregate``, which requires at
        least two hook-captured reviewer artifacts in the session
        ledger; ``--kind reviewer`` remains an unguarded label path —
        its ledger cross-reference is provenance, not admission.

    Args:
        submission_id: ID of the submission
        reviewer: Agent ID of reviewer
        verdict: APPROVED, REJECTED, REQUEST_CHANGES, or ESCALATE
        feedback: Feedback for the submitter
        flagged_rules: List of Constitution rules violated

    Returns:
        True if verdict recorded successfully
    """
    queue = _load_queue()
    for item in queue:
        if item["id"] == submission_id:
            item["status"] = "reviewed"
            item["verdict"] = verdict
            item["feedback"] = feedback
            item["flagged_rules"] = flagged_rules or []
            _save_queue(queue)
            return True

    return False


def list_pending(reviewer: str | None = None) -> list[dict]:
    """List all pending submissions.

    Args:
        reviewer: If set, only show items pending for this reviewer

    Returns:
        List of pending submission dicts
    """
    queue = _load_queue()
    pending = [item for item in queue if item["status"] == "pending"]

    if reviewer:
        pending = [item for item in pending if reviewer in item.get("reviewers", [])]

    return pending


def list_approved(limit: int = 10) -> list[dict]:
    """List recently approved submissions.

    Args:
        limit: Maximum number to return

    Returns:
        List of approved submission dicts
    """
    queue = _load_queue()
    approved = [
        item
        for item in queue
        if item.get("status") == "reviewed" and item.get("verdict") == "APPROVED"
    ]
    return approved[:limit]


def clear_resolved(older_than_days: int = 7) -> int:
    """Remove resolved submissions older than specified days.

    Args:
        older_than_days: Remove items resolved more than this many days ago

    Returns:
        Number of items removed
    """
    from datetime import datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    queue = _load_queue()
    original_count = len(queue)

    remaining = []
    for item in queue:
        if item["status"] == "pending":
            remaining.append(item)
            continue

        verdict_at = item.get("verdict_at", item.get("submitted_at", ""))
        try:
            dt = datetime.fromisoformat(verdict_at.replace("Z", "+00:00"))
            if dt > cutoff:
                remaining.append(item)
        except (ValueError, TypeError, AttributeError):
            remaining.append(item)

    _save_queue(remaining)
    return original_count - len(remaining)


class QualityGateAPI:
    """Class-based API for Quality Gate operations."""

    def __init__(self):
        _ensure_state_dir()

    def submit(
        self,
        title: str,
        description: str,
        deliverable_type: str | None = None,
        submitter: str = "unknown",
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        return submit(title, description, deliverable_type, submitter, metadata)

    def query(self, submission_id: str) -> dict[str, Any] | None:
        return query(submission_id)

    def record_verdict(
        self,
        submission_id: str,
        reviewer: str,
        verdict: str,
        feedback: str = "",
        flagged_rules: list[str] | None = None,
    ) -> bool:
        """Deprecated with the module function — see ``record_verdict``."""
        return record_verdict(submission_id, reviewer, verdict, feedback, flagged_rules)

    def list_pending(self, reviewer: str | None = None) -> list[dict]:
        return list_pending(reviewer)

    def list_approved(self, limit: int = 10) -> list[dict]:
        return list_approved(limit)

    def clear_resolved(self, older_than_days: int = 7) -> int:
        return clear_resolved(older_than_days)
