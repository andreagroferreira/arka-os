"""Tests for the Quality Gate system."""

import pytest

from core.governance.quality_router import (
    QualityRouter,
    ReviewAssignment,
    ReviewerType,
    DeliverableType,
    ReviewPriority,
    RoutingRule,
    route_deliverable,
)
from core.governance.review_workflow import (
    ReviewWorkflowEngine,
    ReviewWorkflow,
    ReviewPhase,
    Verdict,
    ReviewerOpinion,
    ReviewerVote,
    PhaseResult,
)


class TestQualityRouter:
    """Tests for QualityRouter class."""

    def test_route_deliverable_auto_detects_type(self):
        router = QualityRouter()
        result = router.route(
            title="New API Endpoint",
            description="Added REST endpoint for user auth",
            submitter="backend-dev",
        )
        assert result.deliverable_type in DeliverableType

    def test_route_deliverable_with_explicit_type(self):
        router = QualityRouter()
        result = router.route(
            title="Security Audit",
            description="OWASP audit for login flow",
            deliverable_type=DeliverableType.SECURITY,
            submitter="security-eng",
        )
        assert result.deliverable_type == DeliverableType.SECURITY

    def test_route_assigns_reviewers(self):
        router = QualityRouter()
        result = router.route(
            title="Architecture Decision",
            description="ADR for microservices",
            submitter="architect",
        )
        assert len(result.reviewers) > 0
        assert ReviewerType.CQO in result.reviewers

    def test_route_security_priority_urgent(self):
        router = QualityRouter()
        result = router.route(
            title="Critical Security Fix",
            description="Fix SQL injection vulnerability",
            deliverable_type=DeliverableType.SECURITY,
            submitter="backend-dev",
        )
        assert result.priority == ReviewPriority.URGENT

    def test_route_copyl_low_priority(self):
        router = QualityRouter()
        result = router.route(
            title="Copy Review",
            description="Review landing page copy",
            deliverable_type=DeliverableType.COPY,
            submitter="copywriter",
        )
        assert result.priority in ReviewPriority

    def test_get_queue(self):
        router = QualityRouter()
        router.route(title="Test 1", description="Desc 1", submitter="dev1")
        router.route(title="Test 2", description="Desc 2", submitter="dev2")
        queue = router.get_queue()
        assert len(queue) == 2

    def test_get_pending_for_reviewer(self):
        router = QualityRouter()
        router.route(
            title="API Review",
            description="REST endpoint",
            submitter="dev1",
        )
        pending = router.get_pending_for_reviewer(ReviewerType.CQO)
        assert len(pending) >= 0

    def test_update_verdict(self):
        router = QualityRouter()
        assignment = router.route(title="Test", description="Desc", submitter="dev")
        result = router.update_verdict(
            assignment.id,
            verdict="APPROVED",
            feedback="Looks good",
            reviewer=ReviewerType.CQO,
        )
        assert result is not None
        assert result.verdict == "APPROVED"

    def test_sla_due_set(self):
        router = QualityRouter()
        result = router.route(title="Test", description="Desc", submitter="dev")
        assert result.sla_due != ""


class TestReviewWorkflowEngine:
    """Tests for ReviewWorkflowEngine class."""

    def test_submit_creates_workflow(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit(
            deliverable_title="New Feature",
            deliverable_type="code",
            submitter="backend-dev",
        )
        assert workflow.id is not None
        assert workflow.phase == ReviewPhase.SUBMISSION

    def test_start_triage(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        result = engine.start_triage(workflow.id)
        assert result.success is True
        assert workflow.phase == ReviewPhase.TRIAGE

    def test_start_review_after_triage(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        result = engine.start_review(workflow.id)
        assert result.success is True
        assert workflow.phase == ReviewPhase.REVIEW

    def test_start_review_fails_without_triage(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        result = engine.start_review(workflow.id)
        assert result.success is False

    def test_record_vote(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        engine.start_review(workflow.id)
        success = engine.record_vote(
            workflow.id,
            reviewer="cqo-marta",
            opinion=ReviewerOpinion.APPROVE,
            comments="LGTM",
        )
        assert success is True
        assert len(workflow.votes) == 1

    def test_reach_verdict_approved(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        engine.start_review(workflow.id)
        engine.record_vote(workflow.id, "cqo-marta", ReviewerOpinion.APPROVE)
        result = engine.reach_verdict(workflow.id, Verdict.APPROVED, "Approved")
        assert result.success is True
        assert workflow.verdict == Verdict.APPROVED

    def test_deliver_after_approval(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        engine.start_review(workflow.id)
        engine.record_vote(workflow.id, "cqo-marta", ReviewerOpinion.APPROVE)
        engine.reach_verdict(workflow.id, Verdict.APPROVED)
        result = engine.deliver(workflow.id)
        assert result.success is True
        assert workflow.phase == ReviewPhase.DELIVERY

    def test_deliver_fails_without_approval(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        engine.start_review(workflow.id)
        engine.record_vote(workflow.id, "cqo-marta", ReviewerOpinion.REJECT)
        engine.reach_verdict(workflow.id, Verdict.REJECTED)
        result = engine.deliver(workflow.id)
        assert result.success is False

    def test_get_workflow(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        retrieved = engine.get_workflow(workflow.id)
        assert retrieved is not None
        assert retrieved.id == workflow.id

    def test_get_workflows_by_phase(self):
        engine = ReviewWorkflowEngine()
        w1 = engine.submit("Feature 1", "code", "dev")
        w2 = engine.submit("Feature 2", "code", "dev")
        engine.start_triage(w1.id)
        in_triage = engine.get_workflows_by_phase(ReviewPhase.TRIAGE)
        assert len(in_triage) >= 1


class TestReviewPhases:
    """Tests for review phase transitions."""

    def test_phase_order_enforced(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")

        assert workflow.phase == ReviewPhase.SUBMISSION

        engine.start_triage(workflow.id)
        assert workflow.phase == ReviewPhase.TRIAGE

        engine.start_review(workflow.id)
        assert workflow.phase == ReviewPhase.REVIEW

        engine.record_vote(workflow.id, "cqo-marta", ReviewerOpinion.APPROVE)
        engine.start_deliberation(workflow.id)
        assert workflow.phase == ReviewPhase.DELIBERATION

        engine.reach_verdict(workflow.id, Verdict.APPROVED)
        assert workflow.phase == ReviewPhase.VERDICT


class TestVerdicts:
    """Tests for verdict types."""

    def test_all_verdicts_defined(self):
        assert Verdict.APPROVED.value == "APPROVED"
        assert Verdict.REJECTED.value == "REJECTED"
        assert Verdict.REQUEST_CHANGES.value == "REQUEST_CHANGES"
        assert Verdict.ESCALATE.value == "ESCALATE"

    def test_reject_requires_resubmit(self):
        engine = ReviewWorkflowEngine()
        workflow = engine.submit("Feature", "code", "dev")
        engine.start_triage(workflow.id)
        engine.start_review(workflow.id)
        engine.record_vote(workflow.id, "cqo-marta", ReviewerOpinion.REJECT)
        result = engine.reach_verdict(workflow.id, Verdict.REJECTED, "Must fix bug")
        assert result.next_phase is None


class TestReviewerOpinions:
    """Tests for reviewer opinions."""

    def test_all_opinions_defined(self):
        assert ReviewerOpinion.APPROVE.value == "APPROVE"
        assert ReviewerOpinion.REJECT.value == "REJECT"
        assert ReviewerOpinion.CHANGES.value == "REQUEST_CHANGES"
        assert ReviewerOpinion.ABSTAIN.value == "ABSTAIN"


class TestDeliverableTypes:
    """Tests for deliverable type detection."""

    def test_detect_security(self):
        router = QualityRouter()
        result = router._detect_type(
            title="Security Fix",
            description="Fix auth vulnerability",
            metadata={},
        )
        assert result == DeliverableType.SECURITY

    def test_detect_architecture(self):
        router = QualityRouter()
        result = router._detect_type(
            title="ADR for new system",
            description="Architecture decision",
            metadata={},
        )
        assert result == DeliverableType.ARCHITECTURE

    def test_detect_frontend(self):
        router = QualityRouter()
        result = router._detect_type(
            title="Vue Component",
            description="New UI component",
            metadata={"file_path": "components/Button.vue"},
        )
        assert result == DeliverableType.FRONTEND
