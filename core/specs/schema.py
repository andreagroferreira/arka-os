"""Living Spec schema — specs that evolve with implementation.

A Living Spec tracks:
- Original specification (what was planned)
- Implementation status per section
- Deltas (what changed during implementation and why)
- Acceptance criteria with pass/fail status
- Reusable patterns extracted from completed specs
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class SpecStatus(str, Enum):
    DRAFT = "draft"              # Being written
    REVIEW = "review"            # Awaiting user approval
    APPROVED = "approved"        # User approved, ready for implementation
    IN_PROGRESS = "in_progress"  # Implementation started
    COMPLETED = "completed"      # Fully implemented and verified
    ARCHIVED = "archived"        # No longer active


class SectionStatus(str, Enum):
    PENDING = "pending"
    IMPLEMENTED = "implemented"
    MODIFIED = "modified"        # Implemented but deviated from spec
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion with verification status."""
    id: str
    description: str
    status: str = "pending"      # pending, passed, failed
    verified_by: str = ""        # Agent that verified
    verified_at: Optional[str] = None
    notes: str = ""


class SpecSection(BaseModel):
    """A section of the specification."""
    id: str
    title: str
    content: str = ""
    status: SectionStatus = SectionStatus.PENDING
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    implementation_notes: str = ""


class SpecDelta(BaseModel):
    """A recorded change between spec and implementation.

    Deltas track WHY something changed, not just WHAT.
    This builds institutional knowledge for future specs.
    """
    id: str
    section_id: str
    original: str                # What the spec said
    actual: str                  # What was actually implemented
    reason: str                  # Why it changed
    decided_by: str = ""         # Agent or user who decided
    timestamp: str = ""
    impact: str = "low"          # low, medium, high


class SpecMetadata(BaseModel):
    """Metadata for a spec."""
    project: str = ""
    department: str = ""
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    tags: list[str] = Field(default_factory=list)
    obsidian_path: str = ""


class Spec(BaseModel):
    """A Living Specification.

    Unlike traditional specs that become stale, Living Specs
    track their own implementation status and record deltas
    between planned and actual outcomes.
    """
    id: str
    title: str
    description: str = ""
    status: SpecStatus = SpecStatus.DRAFT
    metadata: SpecMetadata = Field(default_factory=SpecMetadata)

    # Spec content organized by sections
    sections: list[SpecSection] = Field(default_factory=list)

    # Changes tracked during implementation
    deltas: list[SpecDelta] = Field(default_factory=list)

    # Reusable patterns extracted after completion
    patterns: list[str] = Field(default_factory=list)

    def get_section(self, section_id: str) -> Optional[SpecSection]:
        """Find a section by ID."""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def add_delta(
        self,
        section_id: str,
        original: str,
        actual: str,
        reason: str,
        decided_by: str = "",
    ) -> SpecDelta:
        """Record a delta between spec and implementation."""
        delta = SpecDelta(
            id=f"delta-{len(self.deltas) + 1}",
            section_id=section_id,
            original=original,
            actual=actual,
            reason=reason,
            decided_by=decided_by,
            timestamp=datetime.now().isoformat(),
        )
        self.deltas.append(delta)

        # Mark section as modified
        section = self.get_section(section_id)
        if section:
            section.status = SectionStatus.MODIFIED

        return delta

    def mark_section_complete(self, section_id: str, notes: str = "") -> bool:
        """Mark a section as implemented."""
        section = self.get_section(section_id)
        if section is None:
            return False
        if section.status != SectionStatus.MODIFIED:
            section.status = SectionStatus.IMPLEMENTED
        section.implementation_notes = notes
        return True

    def verify_criterion(
        self,
        section_id: str,
        criterion_id: str,
        passed: bool,
        verified_by: str = "",
        notes: str = "",
    ) -> bool:
        """Verify an acceptance criterion."""
        section = self.get_section(section_id)
        if section is None:
            return False
        for ac in section.acceptance_criteria:
            if ac.id == criterion_id:
                ac.status = "passed" if passed else "failed"
                ac.verified_by = verified_by
                ac.verified_at = datetime.now().isoformat()
                ac.notes = notes
                return True
        return False

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage based on sections."""
        if not self.sections:
            return 0.0
        done = sum(
            1 for s in self.sections
            if s.status in (SectionStatus.IMPLEMENTED, SectionStatus.MODIFIED, SectionStatus.SKIPPED)
        )
        return round(done / len(self.sections) * 100, 1)

    @property
    def criteria_summary(self) -> dict[str, int]:
        """Summary of acceptance criteria status."""
        counts = {"total": 0, "passed": 0, "failed": 0, "pending": 0}
        for section in self.sections:
            for ac in section.acceptance_criteria:
                counts["total"] += 1
                counts[ac.status] = counts.get(ac.status, 0) + 1
        return counts

    @property
    def delta_count(self) -> int:
        return len(self.deltas)

    @property
    def is_fully_verified(self) -> bool:
        """Check if all acceptance criteria passed."""
        summary = self.criteria_summary
        return summary["total"] > 0 and summary["pending"] == 0 and summary["failed"] == 0
