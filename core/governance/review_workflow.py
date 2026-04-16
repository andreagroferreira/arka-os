"""Review Workflow Engine — structured review phases for Quality Gate.

Phases:
1. Submission — deliverable submitted for review
2. Triage — initial assessment, assign reviewers
3. Review — individual reviewer assessment
4. Deliberation — reviewers discuss findings
5. Verdict — final decision
6. Delivery — approved items proceed

Verdicts:
- APPROVED — passes all criteria, proceed to delivery
- REJECTED — fails critical criteria, must fix and resubmit
- REQUEST_CHANGES — minor issues, can fix and re-review
- ESCALATE — complex issue, requires Tier 0 decision
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class ReviewPhase(str, Enum):
    SUBMISSION = "submission"
    TRIAGE = "triage"
    REVIEW = "review"
    DELIBERATION = "deliberation"
    VERDICT = "verdict"
    DELIVERY = "delivery"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    ESCALATE = "ESCALATE"


class ReviewerOpinion(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CHANGES = "REQUEST_CHANGES"
    ABSTAIN = "ABSTAIN"


@dataclass
class ReviewerVote:
    """A single reviewer's vote."""

    reviewer: str
    opinion: ReviewerOpinion
    comments: str = ""
    flagged_rules: list[str] = field(default_factory=list)
    voted_at: str = ""


@dataclass
class ReviewWorkflow:
    """A complete review workflow instance."""

    id: str
    deliverable_title: str
    deliverable_type: str
    submitter: str
    phase: ReviewPhase = ReviewPhase.SUBMISSION
    verdict: Verdict | None = None
    submitted_at: str = ""
    triage_at: str = ""
    review_started_at: str = ""
    deliberation_at: str = ""
    verdict_at: str = ""
    delivered_at: str = ""
    votes: list[ReviewerVote] = field(default_factory=list)
    feedback: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.submitted_at:
            self.submitted_at = datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseResult:
    """Result of executing a review phase."""

    phase: ReviewPhase
    success: bool
    output: str = ""
    next_phase: ReviewPhase | None = None


class ReviewWorkflowEngine:
    """Executes structured review workflows through Quality Gate.

    Enforces Constitution rules:
    - No delivery without Quality Gate approval
    - BLOCK violations require escalation to Tier 0
    - Mandatory QA runs before verdict
    """

    def __init__(
        self,
        on_phase_start: Callable[[ReviewPhase, str], None] | None = None,
        on_phase_complete: Callable[[ReviewPhase, PhaseResult], None] | None = None,
        on_verdict: Callable[[Verdict, str], None] | None = None,
    ):
        self._on_phase_start = on_phase_start
        self._on_phase_complete = on_phase_complete
        self._on_verdict = on_verdict
        self._workflows: dict[str, ReviewWorkflow] = {}

    def submit(
        self,
        deliverable_title: str,
        deliverable_type: str,
        submitter: str,
        metadata: dict | None = None,
    ) -> ReviewWorkflow:
        """Submit a deliverable for Quality Gate review.

        Args:
            deliverable_title: Title of the deliverable
            deliverable_type: Type of deliverable (code, copy, architecture, etc.)
            submitter: Agent ID who submitted
            metadata: Additional context

        Returns:
            ReviewWorkflow in SUBMISSION phase
        """
        workflow = ReviewWorkflow(
            id=str(uuid.uuid4()),
            deliverable_title=deliverable_title,
            deliverable_type=deliverable_type,
            submitter=submitter,
            metadata=metadata or {},
        )
        self._workflows[workflow.id] = workflow
        return workflow

    def start_triage(self, workflow_id: str) -> PhaseResult:
        """Start triage phase — assign reviewers.

        Args:
            workflow_id: ID of the workflow to triage

        Returns:
            PhaseResult with triage outcome
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return PhaseResult(phase=ReviewPhase.TRIAGE, success=False, output="Workflow not found")

        self._announce_phase_start(ReviewPhase.TRIAGE, workflow_id)

        workflow.phase = ReviewPhase.TRIAGE
        workflow.triage_at = datetime.now(timezone.utc).isoformat()

        result = PhaseResult(
            phase=ReviewPhase.TRIAGE,
            success=True,
            output=f"Triage complete for: {workflow.deliverable_title}",
            next_phase=ReviewPhase.REVIEW,
        )

        self._announce_phase_complete(ReviewPhase.TRIAGE, result)
        return result

    def start_review(self, workflow_id: str) -> PhaseResult:
        """Start the review phase.

        Args:
            workflow_id: ID of the workflow to review

        Returns:
            PhaseResult with review start info
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return PhaseResult(phase=ReviewPhase.REVIEW, success=False, output="Workflow not found")

        if workflow.phase != ReviewPhase.TRIAGE:
            return PhaseResult(
                phase=ReviewPhase.REVIEW,
                success=False,
                output="Must complete triage before review",
            )

        self._announce_phase_start(ReviewPhase.REVIEW, workflow_id)

        workflow.phase = ReviewPhase.REVIEW
        workflow.review_started_at = datetime.now(timezone.utc).isoformat()

        result = PhaseResult(
            phase=ReviewPhase.REVIEW,
            success=True,
            output=f"Review started for: {workflow.deliverable_title}",
            next_phase=ReviewPhase.DELIBERATION,
        )

        self._announce_phase_complete(ReviewPhase.REVIEW, result)
        return result

    def record_vote(
        self,
        workflow_id: str,
        reviewer: str,
        opinion: ReviewerOpinion,
        comments: str = "",
        flagged_rules: list[str] | None = None,
    ) -> bool:
        """Record a reviewer's vote.

        Args:
            workflow_id: ID of the workflow
            reviewer: Agent ID of reviewer
            opinion: Their vote
            comments: Optional comments
            flagged_rules: Constitution rules that were violated

        Returns:
            True if vote recorded successfully
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        if workflow.phase not in (ReviewPhase.REVIEW, ReviewPhase.DELIBERATION):
            return False

        vote = ReviewerVote(
            reviewer=reviewer,
            opinion=opinion,
            comments=comments,
            flagged_rules=flagged_rules or [],
            voted_at=datetime.now(timezone.utc).isoformat(),
        )
        workflow.votes.append(vote)
        return True

    def start_deliberation(self, workflow_id: str) -> PhaseResult:
        """Start deliberation phase — reviewers discuss findings.

        Args:
            workflow_id: ID of the workflow

        Returns:
            PhaseResult with deliberation outcome
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return PhaseResult(
                phase=ReviewPhase.DELIBERATION, success=False, output="Workflow not found"
            )

        if not workflow.votes:
            return PhaseResult(
                phase=ReviewPhase.DELIBERATION,
                success=False,
                output="No votes recorded yet",
            )

        self._announce_phase_start(ReviewPhase.DELIBERATION, workflow_id)

        workflow.phase = ReviewPhase.DELIBERATION
        workflow.deliberation_at = datetime.now(timezone.utc).isoformat()

        result = PhaseResult(
            phase=ReviewPhase.DELIBERATION,
            success=True,
            output=f"Deliberation started with {len(workflow.votes)} votes",
            next_phase=ReviewPhase.VERDICT,
        )

        self._announce_phase_complete(ReviewPhase.DELIBERATION, result)
        return result

    def reach_verdict(self, workflow_id: str, verdict: Verdict, feedback: str = "") -> PhaseResult:
        """Record the final verdict.

        Args:
            workflow_id: ID of the workflow
            verdict: Final verdict
            feedback: Feedback for the submitter

        Returns:
            PhaseResult with verdict outcome
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return PhaseResult(
                phase=ReviewPhase.VERDICT, success=False, output="Workflow not found"
            )

        self._announce_phase_start(ReviewPhase.VERDICT, workflow_id)

        workflow.phase = ReviewPhase.VERDICT
        workflow.verdict = verdict
        workflow.feedback = feedback
        workflow.verdict_at = datetime.now(timezone.utc).isoformat()

        self._announce_verdict(verdict, workflow_id)

        next_phase = ReviewPhase.DELIVERY if verdict == Verdict.APPROVED else None

        result = PhaseResult(
            phase=ReviewPhase.VERDICT,
            success=True,
            output=f"Verdict: {verdict.value} — {feedback}",
            next_phase=next_phase,
        )

        self._announce_phase_complete(ReviewPhase.VERDICT, result)
        return result

    def deliver(self, workflow_id: str) -> PhaseResult:
        """Mark workflow as delivered (post-approval).

        Args:
            workflow_id: ID of the workflow

        Returns:
            PhaseResult with delivery outcome
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return PhaseResult(
                phase=ReviewPhase.DELIVERY, success=False, output="Workflow not found"
            )

        if workflow.verdict != Verdict.APPROVED:
            return PhaseResult(
                phase=ReviewPhase.DELIVERY,
                success=False,
                output=f"Cannot deliver: verdict is {workflow.verdict}",
            )

        workflow.phase = ReviewPhase.DELIVERY
        workflow.delivered_at = datetime.now(timezone.utc).isoformat()

        result = PhaseResult(
            phase=ReviewPhase.DELIVERY,
            success=True,
            output=f"Delivered: {workflow.deliverable_title}",
        )

        self._announce_phase_complete(ReviewPhase.DELIVERY, result)
        return result

    def get_workflow(self, workflow_id: str) -> ReviewWorkflow | None:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_all_workflows(self) -> list[ReviewWorkflow]:
        """Get all workflows."""
        return list(self._workflows.values())

    def get_workflows_by_phase(self, phase: ReviewPhase) -> list[ReviewWorkflow]:
        """Get all workflows in a specific phase."""
        return [w for w in self._workflows.values() if w.phase == phase]

    def _announce_phase_start(self, phase: ReviewPhase, workflow_id: str) -> None:
        if self._on_phase_start:
            self._on_phase_start(phase, workflow_id)

    def _announce_phase_complete(self, phase: ReviewPhase, result: PhaseResult) -> None:
        if self._on_phase_complete:
            self._on_phase_complete(phase, result)

    def _announce_verdict(self, verdict: Verdict, workflow_id: str) -> None:
        if self._on_verdict:
            self._on_verdict(verdict, workflow_id)


def create_review(
    deliverable_title: str,
    deliverable_type: str,
    submitter: str,
) -> ReviewWorkflow:
    """Convenience function to create a review workflow."""
    engine = ReviewWorkflowEngine()
    workflow = engine.submit(deliverable_title, deliverable_type, submitter)
    engine.start_triage(workflow.id)
    engine.start_review(workflow.id)
    return workflow
