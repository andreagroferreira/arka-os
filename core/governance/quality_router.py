"""Quality Gate Router — auto-routes deliverables to appropriate reviewers.

Routes deliverables to:
- Marta (CQO): Architecture, security, technical decisions
- Eduardo (Copy): All text, copy, documentation, content
- Francisca (Tech UX): UI/UX, frontend, user-facing code

Features:
- Automatic routing based on deliverable type
- Priority queuing
- SLA tracking (24h default)
- Escalation on BLOCK violations
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class ReviewerType(str, Enum):
    CQO = "cqo-marta"  # Marta - Chief Quality Officer
    COPY = "copy-eduardo"  # Eduardo - Copy Director
    TECH_UX = "tech-francisca"  # Francisca - Tech UX


class DeliverableType(str, Enum):
    CODE = "code"  # Backend/API code
    FRONTEND = "frontend"  # UI/UX, Vue/React
    ARCHITECTURE = "architecture"  # ADRs, system design
    SECURITY = "security"  # Security audits, auth
    COPY = "copy"  # Text, docs, content
    DOCUMENTATION = "documentation"  # Docs, READMEs
    STRATEGY = "strategy"  # Plans, roadmaps
    DATA = "data"  # Models, migrations


class ReviewPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ReviewAssignment:
    """A deliverable assigned for review."""

    id: str
    deliverable_type: DeliverableType
    title: str
    description: str
    submitter: str
    submitted_at: str
    reviewers: list[ReviewerType]
    priority: ReviewPriority = ReviewPriority.NORMAL
    status: str = "pending"
    verdict: str = ""
    feedback: str = ""
    sla_due: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.sla_due:
            self.sla_due = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()


@dataclass
class RoutingRule:
    """A rule for routing deliverables to reviewers."""

    deliverable_types: list[DeliverableType]
    keywords: list[str]
    file_extensions: list[str]
    reviewers: list[ReviewerType]
    priority: ReviewPriority = ReviewPriority.NORMAL


DEFAULT_ROUTING_RULES: list[RoutingRule] = [
    RoutingRule(
        deliverable_types=[DeliverableType.ARCHITECTURE],
        keywords=["architecture", "adr", "system design", "decision"],
        file_extensions=[".md"],
        reviewers=[ReviewerType.CQO],
        priority=ReviewPriority.HIGH,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.SECURITY],
        keywords=["security", "auth", "permission", "oauth", "jwt"],
        file_extensions=[],
        reviewers=[ReviewerType.CQO, ReviewerType.TECH_UX],
        priority=ReviewPriority.URGENT,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.FRONTEND],
        keywords=["vue", "react", "ui", "component", "tailwind", "css"],
        file_extensions=[".vue", ".tsx", ".jsx"],
        reviewers=[ReviewerType.TECH_UX],
        priority=ReviewPriority.NORMAL,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.CODE],
        keywords=["api", "backend", "service", "model", "controller"],
        file_extensions=[".py", ".php", ".java", ".go"],
        reviewers=[ReviewerType.CQO],
        priority=ReviewPriority.NORMAL,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.COPY],
        keywords=["copy", "headline", "cta", "landing", "sales"],
        file_extensions=[],
        reviewers=[ReviewerType.COPY],
        priority=ReviewPriority.NORMAL,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.DOCUMENTATION],
        keywords=["doc", "readme", "guide", "docs"],
        file_extensions=[".md", ".txt"],
        reviewers=[ReviewerType.COPY, ReviewerType.TECH_UX],
        priority=ReviewPriority.LOW,
    ),
    RoutingRule(
        deliverable_types=[DeliverableType.STRATEGY],
        keywords=["roadmap", "strategy", "plan", "okr", "kpi"],
        file_extensions=[".md"],
        reviewers=[ReviewerType.CQO, ReviewerType.COPY],
        priority=ReviewPriority.HIGH,
    ),
]


class QualityRouter:
    """Routes deliverables to appropriate Quality Gate reviewers."""

    def __init__(self, rules: list[RoutingRule] | None = None):
        self.rules = rules or DEFAULT_ROUTING_RULES
        self._queue: list[ReviewAssignment] = []

    def route(
        self,
        title: str,
        description: str,
        deliverable_type: DeliverableType | None = None,
        submitter: str = "unknown",
        metadata: dict | None = None,
    ) -> ReviewAssignment:
        """Route a deliverable to appropriate reviewers.

        Args:
            title: Deliverable title
            description: Brief description
            deliverable_type: Explicit type (auto-detected if None)
            submitter: Agent ID of submitter
            metadata: Additional context

        Returns:
            ReviewAssignment with assigned reviewers
        """
        if deliverable_type is None:
            deliverable_type = self._detect_type(title, description, metadata)

        reviewers = self._find_reviewers(deliverable_type, title, description, metadata)
        priority = self._find_priority(deliverable_type, title, description)

        assignment = ReviewAssignment(
            id=str(uuid.uuid4()),
            deliverable_type=deliverable_type,
            title=title,
            description=description,
            submitter=submitter,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            reviewers=reviewers,
            priority=priority,
            metadata=metadata or {},
        )

        self._queue.append(assignment)
        return assignment

    def _detect_type(
        self,
        title: str,
        description: str,
        metadata: dict | None,
    ) -> DeliverableType:
        """Auto-detect deliverable type from content."""
        text = f"{title} {description}".lower()
        metadata = metadata or {}

        if any(kw in text for kw in ["security", "auth", "permission", "oauth"]):
            return DeliverableType.SECURITY
        if any(kw in text for kw in ["architecture", "adr", "system design"]):
            return DeliverableType.ARCHITECTURE
        if any(kw in text for kw in ["vue", "react", "ui", "component", "frontend"]):
            return DeliverableType.FRONTEND
        if any(kw in text for kw in ["api", "backend", "service", "model"]):
            return DeliverableType.CODE
        if any(kw in text for kw in ["copy", "headline", "cta", "sales", "landing"]):
            return DeliverableType.COPY
        if any(kw in text for kw in ["doc", "readme", "guide"]):
            return DeliverableType.DOCUMENTATION
        if any(kw in text for kw in ["roadmap", "strategy", "plan"]):
            return DeliverableType.STRATEGY

        if metadata.get("file_path"):
            ext = Path(metadata["file_path"]).suffix.lower()
            if ext in [".vue", ".tsx", ".jsx"]:
                return DeliverableType.FRONTEND
            if ext in [".py", ".php", ".java", ".go"]:
                return DeliverableType.CODE

        return DeliverableType.CODE

    def _find_reviewers(
        self,
        deliverable_type: DeliverableType,
        title: str,
        description: str,
        metadata: dict | None,
    ) -> list[ReviewerType]:
        """Find appropriate reviewers for this deliverable."""
        for rule in self.rules:
            if deliverable_type in rule.deliverable_types:
                return rule.reviewers

        return [ReviewerType.CQO]

    def _find_priority(
        self,
        deliverable_type: DeliverableType,
        title: str,
        description: str,
    ) -> ReviewPriority:
        """Determine review priority."""
        text = f"{title} {description}".lower()

        if any(kw in text for kw in ["urgent", "asap", "critical", "blocker"]):
            return ReviewPriority.URGENT

        for rule in self.rules:
            if deliverable_type in rule.deliverable_types:
                return rule.priority

        return ReviewPriority.NORMAL

    def get_queue(self) -> list[ReviewAssignment]:
        """Get current review queue."""
        return self._queue.copy()

    def get_pending_for_reviewer(self, reviewer: ReviewerType) -> list[ReviewAssignment]:
        """Get pending items for a specific reviewer."""
        return [a for a in self._queue if reviewer in a.reviewers and a.status == "pending"]

    def get_assignment(self, assignment_id: str) -> ReviewAssignment | None:
        """Get a specific assignment by ID."""
        for a in self._queue:
            if a.id == assignment_id:
                return a
        return None

    def update_verdict(
        self,
        assignment_id: str,
        verdict: str,
        feedback: str,
        reviewer: ReviewerType,
    ) -> ReviewAssignment | None:
        """Record a verdict for an assignment."""
        assignment = self.get_assignment(assignment_id)
        if not assignment:
            return None

        if reviewer not in assignment.reviewers:
            return None

        assignment.verdict = verdict
        assignment.feedback = feedback
        assignment.status = "reviewed"
        return assignment

    def is_sla_breached(self, assignment: ReviewAssignment) -> bool:
        """Check if an assignment has breached SLA."""
        try:
            due = datetime.fromisoformat(assignment.sla_due)
            return datetime.now(timezone.utc) > due
        except (ValueError, TypeError):
            return False

    def get_breached_items(self) -> list[ReviewAssignment]:
        """Get all assignments that have breached SLA."""
        return [a for a in self._queue if self.is_sla_breached(a) and a.status == "pending"]


def route_deliverable(
    title: str,
    description: str,
    deliverable_type: DeliverableType | None = None,
    submitter: str = "unknown",
) -> ReviewAssignment:
    """Convenience function to route a deliverable."""
    router = QualityRouter()
    return router.route(title, description, deliverable_type, submitter)
